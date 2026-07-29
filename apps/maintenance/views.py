from collections import defaultdict
from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.alerts.models import AlertStatus
from apps.alerts.services import broadcast_alert_event
from apps.audit.services import log_activity
from apps.common.permissions import IsAdmin, IsAdminOrManager, IsController, IsMaintenance

from .models import Intervention, PmStatus, PreventiveMaintenance
from .serializers import (
    InterventionFinishSerializer, InterventionSerializer,
    PreventiveMaintenanceSerializer,
)


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
