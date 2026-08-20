from collections import defaultdict
from datetime import datetime, timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.alerts.models import AlertStatus
from apps.alerts.services import broadcast_alert_event, sync_machine_andon_status
from apps.audit.services import log_activity
from apps.common.permissions import IsAdmin, IsAdminOrManager, IsController, IsMaintenance
from apps.machines.models import AuxiliaryEquipment, Machine

from .models import (
    ChecklistItem, ChecklistTemplate, ControlResultStatus, Intervention,
    MaintenanceControl, MaintenanceControlResult, PmStatus, PreventiveMaintenance,
)
from .serializers import (
    ChecklistTemplateSerializer, InterventionFinishSerializer,
    InterventionSerializer, MaintenanceControlSerializer,
    MaintenanceControlStartSerializer, MaintenanceControlSubmitResultsSerializer,
    PreventiveMaintenanceSerializer,
)
from .services import resolve_template

CAN_RUN_CONTROL = ("CONTROLLER",)


@extend_schema(tags=["Maintenance"])
class InterventionViewSet(viewsets.ModelViewSet):
    queryset = Intervention.objects.select_related("alert", "technician")
    serializer_class = InterventionSerializer
    permission_classes = (IsAuthenticated, IsAdmin | IsMaintenance | IsAdminOrManager)
    filterset_fields = ("technician", "alert__machine")
    search_fields = ("action_taken", "parts_used")
    ordering = ["-started_at"]

    def perform_create(self, serializer):
        if self.request.user.role not in ("ADMIN", "MANAGER", "MAINTENANCE"):
            raise ValidationError("Rôle insuffisant pour créer une intervention.")
        serializer.save(
            technician=self.request.user if self.request.user.role == "MAINTENANCE" else serializer.validated_data.get("technician"),
        )

    @action(detail=True, methods=["patch"])
    def finish(self, request, pk=None):
        iv = self.get_object()
        if iv.finished_at:
            raise ValidationError("Intervention déjà terminée.")
        ser = InterventionFinishSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        iv.finished_at = timezone.now()
        if not iv.technician_id:
            iv.technician = request.user
        for k in ("action_taken", "parts_used", "notes"):
            if ser.validated_data.get(k) is not None:
                setattr(iv, k, ser.validated_data[k])
        iv.save()

        # Single-step approval: maintenance finishing the intervention IS the
        # confirmation the problem is solved, so resolve the linked alert too.
        alert = iv.alert
        if alert.can_resolve(request.user):
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = timezone.now()
            alert.resolved_by = request.user
            alert.save()
            broadcast_alert_event(alert, "alert.resolved", extra={"resolved_by": request.user.full_name})
            sync_machine_andon_status(alert.machine)

        log_activity(request.user, "intervention.finished", "Intervention", iv.pk, iv.action_taken)
        return Response(InterventionSerializer(iv).data)

    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated, IsAdmin | IsAdminOrManager | IsController])
    def verify(self, request, pk=None):
        iv = self.get_object()
        if not iv.finished_at:
            raise ValidationError("Impossible de vérifier une intervention non terminée.")
        if iv.verified:
            raise ValidationError("Intervention déjà vérifiée.")
        iv.verified = True
        iv.save()
        log_activity(request.user, "intervention.verified", "Intervention", iv.pk)
        return Response(InterventionSerializer(iv).data)

    @action(detail=False, methods=["get"])
    def my_tasks(self, request):
        rows = self.queryset.filter(technician=request.user, finished_at__isnull=True)
        return Response(InterventionSerializer(rows, many=True).data)

    @action(detail=False, methods=["get"])
    def queue(self, request):
        """Every unfinished intervention, regardless of who (if anyone) picked it up.

        This is how maintenance "notices" problems controllers just declared:
        as soon as an alert is created, an Intervention exists here with no
        technician yet — whoever finishes it claims it in the same action.
        """
        rows = self.queryset.filter(finished_at__isnull=True)
        return Response(InterventionSerializer(rows, many=True).data)

    @action(detail=False, methods=["get"])
    def by_day(self, request):
        """Every intervention active on a given day — started that day OR
        finished that day — whether still in progress or already terminée.
        Unlike `queue`, finishing one doesn't make it disappear from here;
        it's how maintenance sees everything they've handled for the day,
        not just what's still outstanding."""
        date_str = request.query_params.get("date")
        try:
            date_val = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else timezone.now().date()
        except ValueError:
            raise ValidationError("Date invalide, format attendu YYYY-MM-DD.")
        rows = self.queryset.filter(
            Q(started_at__date=date_val) | Q(finished_at__date=date_val)
        )
        return Response(InterventionSerializer(rows, many=True).data)

    @action(detail=False, methods=["get"])
    def mttr(self, request):
        days = int(request.query_params.get("days", 30))
        start = timezone.now() - timedelta(days=days)
        closed = Intervention.objects.filter(finished_at__isnull=False, started_at__gte=start)
        per_machine = closed.values("alert__machine__code").annotate(
            count=Count("id"), avg=Avg("duration_min"),
        )
        out = [
            {
                "machine_code": row["alert__machine__code"],
                "interventions": row["count"],
                "mttr_min": round(row["avg"], 1) if row["avg"] else 0,
            }
            for row in per_machine
        ]
        avg_all = closed.aggregate(avg=Avg("duration_min")).get("avg") or 0
        return Response({"window_days": days, "mttr_global_min": round(avg_all, 1), "rows": out})


@extend_schema(tags=["Maintenance"])
class PreventiveMaintenanceViewSet(viewsets.ModelViewSet):
    queryset = PreventiveMaintenance.objects.select_related("machine", "assigned_to")
    serializer_class = PreventiveMaintenanceSerializer
    permission_classes = (IsAuthenticated, IsAdmin | IsAdminOrManager | IsMaintenance)
    filterset_fields = ("machine", "status", "frequency", "assigned_to")
    search_fields = ("task",)
    ordering = ["next_due"]

    def perform_create(self, serializer):
        if self.request.user.role not in ("ADMIN", "MANAGER", "MAINTENANCE"):
            raise PermissionDenied("Rôle insuffisant pour créer une tâche préventive.")
        serializer.save()

    @action(detail=False, methods=["get"])
    def due(self, request):
        rows = self.get_queryset().filter(status__in=[PmStatus.DUE, PmStatus.OVERDUE])
        return Response(PreventiveMaintenanceSerializer(rows, many=True).data)


# ─────────────────────── Controller "Control" page (plan.md §12) ───────────────────────

@extend_schema(tags=["Maintenance"])
class ChecklistTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """Seeded once from the PDF, not user-editable in v1 — read-only."""
    queryset = ChecklistTemplate.objects.filter(is_active=True).prefetch_related("sections__items")
    serializer_class = ChecklistTemplateSerializer
    permission_classes = (IsAuthenticated,)


@extend_schema(tags=["Maintenance"])
class MaintenanceControlViewSet(viewsets.ReadOnlyModelViewSet):
    """Creation only happens through `start` (get-or-create + auto-populate
    results from the target's template), never a plain POST — that's what
    keeps 'exactly one of machine/equipment' true by construction instead of
    needing model-level validation."""
    queryset = MaintenanceControl.objects.select_related(
        "template", "machine", "equipment", "controller", "confirmed_by",
    ).prefetch_related("results__item__section")
    serializer_class = MaintenanceControlSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("machine", "equipment", "shift", "date", "template", "controller")
    ordering = ["-date", "-id"]

    @action(detail=False, methods=["post"])
    def start(self, request):
        if request.user.role not in CAN_RUN_CONTROL:
            raise PermissionDenied("Rôle insuffisant pour démarrer un contrôle préventif.")
        ser = MaintenanceControlStartSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        machine = None
        equipment = None
        if data.get("machine"):
            machine = Machine.objects.filter(pk=data["machine"]).first()
            if not machine:
                raise ValidationError("Machine introuvable.")
        else:
            equipment = AuxiliaryEquipment.objects.filter(pk=data["equipment"]).first()
            if not equipment:
                raise ValidationError("Équipement introuvable.")

        template = resolve_template(machine=machine, equipment=equipment)

        control, created = MaintenanceControl.objects.get_or_create(
            date=data["date"], shift=data["shift"], template=template,
            machine=machine, equipment=equipment,
            defaults={"controller": request.user},
        )
        if created:
            items = ChecklistItem.objects.filter(section__template=template)
            MaintenanceControlResult.objects.bulk_create([
                MaintenanceControlResult(control=control, item=item) for item in items
            ])
            log_activity(
                request.user, "maintenance_control.started", "MaintenanceControl", control.pk,
                f"{control.target_label} — {control.date} {control.shift}",
            )

        control.refresh_from_db()
        return Response(
            MaintenanceControlSerializer(control).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["patch"], url_path="results")
    def submit_results(self, request, pk=None):
        control = self.get_object()
        if request.user.role not in CAN_RUN_CONTROL:
            raise PermissionDenied("Rôle insuffisant pour saisir un contrôle préventif.")
        if control.is_locked():
            raise ValidationError("Ce contrôle est déjà confirmé — verrouillé.")

        ser = MaintenanceControlSubmitResultsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        results_by_item = {r.item_id: r for r in control.results.all()}
        for row in ser.validated_data["results"]:
            result = results_by_item.get(row["item"])
            if not result:
                raise ValidationError(f"Élément de checklist {row['item']} introuvable pour ce contrôle.")
            result.status = row["status"]
            result.note = row.get("note", "")
            result.save()

        control.refresh_from_db()
        return Response(MaintenanceControlSerializer(control).data)

    @action(detail=True, methods=["patch"])
    def confirm(self, request, pk=None):
        control = self.get_object()
        if request.user.role not in CAN_RUN_CONTROL:
            raise PermissionDenied("Rôle insuffisant pour confirmer un contrôle préventif.")
        if control.is_locked():
            raise ValidationError("Ce contrôle est déjà confirmé.")

        # One confirmation per controller per day, across every machine/equipment —
        # the first "Confirmer le contrôle" of the day is also the last.
        already_confirmed_today = MaintenanceControl.objects.filter(
            confirmed_by=request.user, date=control.date,
        ).exclude(pk=control.pk).exists()
        if already_confirmed_today:
            raise ValidationError("Vous avez déjà confirmé un contrôle aujourd'hui — un seul contrôle peut être confirmé par jour.")

        missing_notes = control.results.filter(status=ControlResultStatus.PROBLEM, note="")
        if missing_notes.exists():
            raise ValidationError("Une note est requise pour chaque élément marqué « Problème ».")

        control.confirmed_at = timezone.now()
        control.confirmed_by = request.user
        control.save()
        log_activity(
            request.user, "maintenance_control.confirmed", "MaintenanceControl", control.pk,
            f"{control.target_label} — {control.date} {control.shift}",
        )
        return Response(MaintenanceControlSerializer(control).data)
