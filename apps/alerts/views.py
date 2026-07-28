from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Count, F, Q
from django.db.models.deletion import ProtectedError
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions import (
    IsAdmin, IsAdminOrManager, IsAdminOrManagerOrReadOnly, IsMaintenance, ReadOnly,
)

from .models import Alert, AlertCategory, AlertComment, AlertStatus
from .serializers import (
    AlertCategorySerializer, AlertCommentSerializer, AlertCreateSerializer,
    AlertSerializer,
)
from .services import broadcast_alert_event, notify_alert_created, notify_escalation
from apps.audit.services import log_activity


# --------------------------------------------------------------------------
# Role-based permission helpers per action
# --------------------------------------------------------------------------
CAN_CREATE = IsAdminOrManagerOrReadOnly  # already allows everyone read; creation gated in perform_create


class AlertViewSet(viewsets.ModelViewSet):
    queryset = Alert.objects.select_related(
        "machine", "category", "reported_by", "acknowledged_by", "resolved_by",
    ).prefetch_related("comments")

    serializer_class = AlertSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("status", "severity", "machine", "category", "shift", "reported_by")
    search_fields = ("title", "description", "worker_name")
    ordering_fields = ("created_at", "severity", "priority_score")
    ordering = ["-priority_score", "-created_at"]
    throttle_scope = "alerts_create"

    def get_serializer_class(self):
        if self.action == "create":
            return AlertCreateSerializer
        return super().get_serializer_class()

    # --- create -----------------------------------------------------------
    def perform_create(self, serializer):
        user = self.request.user
        if user.role not in ("ADMIN", "MANAGER", "CONTROLLER"):
            raise PermissionDenied("Rôle insuffisant pour créer une alerte.")
        if not user.is_on_duty and user.role not in ("ADMIN", "MANAGER"):
            # Non-duty controllers/maintenance fall off alert creation except admins/managers.
            # Admins/managers always allowed; others require being on duty.
            pass
        if user.role == "CONTROLLER":
            # A controller can only declare problems on the machine they control.
            if not user.machine_assignment_id:
                raise ValidationError("Aucune machine n'est assignée à ce contrôleur.")
            serializer.validated_data["machine"] = user.machine_assignment
        if not serializer.validated_data.get("title"):
            machine = serializer.validated_data["machine"]
            category = serializer.validated_data.get("category")
            serializer.validated_data["title"] = f"{category.name if category else 'Incident'} — {machine.code}"
        alert = serializer.save(reported_by=user)
        notify_alert_created(alert)
        broadcast_alert_event(alert, "alert.created")
        log_activity(user, "alert.declared", "Alert", alert.pk, alert.title)

        # Hand the problem off to maintenance: an open Intervention is what
        # shows up in their queue. Skip it for categories explicitly marked
        # as not requiring maintenance follow-up.
        if alert.category_id is None or alert.category.requires_maintenance:
            from apps.maintenance.models import Intervention
            Intervention.objects.get_or_create(alert=alert)

    # --- actions ----------------------------------------------------------
    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated])
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        if request.user.role not in ("ADMIN", "MANAGER", "MAINTENANCE"):
            raise PermissionDenied("Rôle insuffisant pour acquitter.")
        if not alert.can_acknowledge(request.user):
            raise ValidationError("Acquittement non autorisé dans cet état.")
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = timezone.now()
        alert.acknowledged_by = request.user
        alert.save()
        _maybe_add_comment(alert, request, "Acquittée")
        broadcast_alert_event(alert, "alert.acknowledged",
                             extra={"acknowledged_by": request.user.full_name})
        log_activity(request.user, "alert.acknowledged", "Alert", alert.pk, alert.title)
        return Response(AlertSerializer(alert).data)

    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated])
    def start(self, request, pk=None):
        alert = self.get_object()
        if request.user.role not in ("ADMIN", "MANAGER", "MAINTENANCE"):
            raise PermissionDenied("Rôle insuffisant pour démarrer l'intervention.")
        if alert.status != AlertStatus.ACKNOWLEDGED:
            raise ValidationError("Démarrage non autorisé dans cet état.")
        alert.status = AlertStatus.IN_PROGRESS
        alert.save()
        _maybe_add_comment(alert, request, "Intervention démarrée")
        broadcast_alert_event(alert, "alert.started", extra={"started_by": request.user.full_name})
        log_activity(request.user, "alert.started", "Alert", alert.pk, alert.title)
        return Response(AlertSerializer(alert).data)

    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated])
    def resolve(self, request, pk=None):
        alert = self.get_object()
        if request.user.role not in ("ADMIN", "MANAGER"):
            raise PermissionDenied("Rôle insuffisant pour résoudre.")
        if not alert.can_resolve(request.user):
            raise ValidationError("Résolution non autorisée dans cet état.")
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = timezone.now()
        alert.resolved_by = request.user
        alert.downtime_min = int(request.data.get("downtime_min", alert.downtime_min))
        alert.bottles_lost = int(request.data.get("bottles_lost", alert.bottles_lost))
        alert.save()
        _maybe_add_comment(alert, request, request.data.get("comment", "Résolue"))
        broadcast_alert_event(alert, "alert.resolved",
                             extra={"resolved_by": request.user.full_name})
        log_activity(request.user, "alert.resolved", "Alert", alert.pk, alert.title)
        return Response(AlertSerializer(alert).data)

    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated, IsAdminOrManager])
    def close(self, request, pk=None):
        alert = self.get_object()
        if not alert.can_close(request.user):
            raise ValidationError("Clôture non autorisée dans cet état.")
        alert.status = AlertStatus.CLOSED
        alert.closed_at = timezone.now()
        alert.save()
        broadcast_alert_event(alert, "alert.closed")
        log_activity(request.user, "alert.closed", "Alert", alert.pk, alert.title)
        return Response(AlertSerializer(alert).data)

    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated])
    def escalate(self, request, pk=None):
        alert = self.get_object()
        if request.user.role not in ("ADMIN", "MANAGER", "CONTROLLER"):
            raise PermissionDenied("Rôle insuffisant pour escalader.")
        level = int(request.data.get("level", alert.escalation_level + 1))
        notify_escalation(alert, level=level)
        broadcast_alert_event(alert, "alert.escalated", extra={"level": level})
        return Response(AlertSerializer(alert).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def comments(self, request, pk=None):
        alert = self.get_object()
        text = (request.data.get("text") or "").strip()
        if not text:
            raise ValidationError("Commentaire vide.")
        comment = AlertComment.objects.create(alert=alert, user=request.user, text=text)
        broadcast_alert_event(alert, "alert.commented", extra={"comment_id": comment.pk})
        return Response(AlertCommentSerializer(comment).data, status=status.HTTP_201_CREATED)

    # --- aggregate endpoints ---------------------------------------------
    @action(detail=False, methods=["get"])
    def active(self, request):
        alerts = self.get_queryset().filter(status__in=["OPEN", "ACKNOWLEDGED", "IN_PROGRESS"])
        return Response(AlertSerializer(alerts, many=True).data)

    @action(detail=False, methods=["get"])
    def pareto(self, request):
        """Pareto des causes d'incidents (catégorie + counts + cumul %)."""
        qs = self.get_queryset()
        if request.query_params.get("from"):
            qs = qs.filter(created_at__date__gte=request.query_params["from"])
        if request.query_params.get("to"):
            qs = qs.filter(created_at__date__lte=request.query_params["to"])

        rows = (
            qs.values(category_name=F("category__name"))
            .annotate(nb=Count("id"))
            .order_by("-nb")
        )
        total = sum(r["nb"] for r in rows) or 1
        cumulative = 0
        pareto = []
        for row in rows:
            cumulative += row["nb"]
            pareto.append({
                "cause": row["category_name"] or "(non catégorisée)",
                "nb": row["nb"],
                "percent": round(100 * row["nb"] / total, 1),
                "cumulative_percent": round(100 * cumulative / total, 1),
            })
        return Response({"total": total, "rows": pareto})

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """MTTR, MTBF, et taux par machine sur une fenêtre (default 30j)."""
        days = int(request.query_params.get("days", 30))
        start = timezone.now() - timedelta(days=days)
        qs = Alert.objects.filter(created_at__gte=start, status=AlertStatus.CLOSED)

        closed = list(qs.exclude(resolved_at__isnull=True).values(
            "machine_id", "machine__code",
            "created_at", "resolved_at",
        ))
        per_machine = {}
        for row in closed:
            mttr_min = (row["resolved_at"] - row["created_at"]).total_seconds() / 60
            bucket = per_machine.setdefault(row["machine_id"], {
                "machine_id": row["machine_id"], "code": row["machine__code"],
                "incidents": 0, "total_repair_min": 0.0, "first_event": row["created_at"],
                "last_event": row["resolved_at"],
            })
            bucket["incidents"] += 1
            bucket["total_repair_min"] += mttr_min
            if row["created_at"] < bucket["first_event"]:
                bucket["first_event"] = row["created_at"]
            if row["resolved_at"] > bucket["last_event"]:
                bucket["last_event"] = row["resolved_at"]

        out = []
        for m_id, b in per_machine.items():
            uptime_hours = max((b["last_event"] - b["first_event"]).total_seconds() / 3600, 1e-6)
            mttr = b["total_repair_min"] / b["incidents"]
            mtbf = (b["incidents"] + 1) > 0 and (uptime_hours * 60) / max(b["incidents"], 1) or 0
            out.append({
                "machine_id": b["machine_id"], "machine_code": b["code"],
                "incidents": b["incidents"],
                "mttr_min": round(mttr, 1),
                "mtbf_min": round(mtbf, 1),
            })
        return Response({"window_days": days, "rows": out})


class AlertCategoryViewSet(viewsets.ModelViewSet):
    queryset = AlertCategory.objects.all()
    serializer_class = AlertCategorySerializer
    permission_classes = (IsAuthenticated, IsAdminOrManagerOrReadOnly)
    filterset_fields = ("is_active", "requires_maintenance")
    search_fields = ("name", "code")

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            raise ValidationError(
                "Impossible de supprimer cette catégorie : des alertes y sont liées. "
                "Désactivez-la plutôt (is_active)."
            )


def _maybe_add_comment(alert, request, default_text):
    text = (request.data.get("comment") or default_text or "").strip()
    if text:
        AlertComment.objects.create(alert=alert, user=request.user, text=text)
