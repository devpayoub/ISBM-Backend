from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import log_activity
from apps.common.permissions import IsAdminOrManagerOrReadOnly
from apps.machines.models import Machine

from .models import PlanningOrder, PlanningOrderStatus, ProductionPlan
from .serializers import PlanningOrderSerializer, ProductionPlanSerializer
from .services import calculate_schedule

# plan.md §2: Admin "creates/manages planning inputs and priorities" — not
# a Controller/Operator capability.
MANAGE_ROLES = ("ADMIN", "MANAGER")


@extend_schema(tags=["Planning"])
class ProductionPlanViewSet(viewsets.ModelViewSet):
    queryset = ProductionPlan.objects.select_related("machine").all()
    serializer_class = ProductionPlanSerializer
    permission_classes = (IsAuthenticated, IsAdminOrManagerOrReadOnly)
    filterset_fields = ("date", "machine", "product")
    search_fields = ("product", "notes")
    ordering = ["-date", "machine__code"]

    @action(detail=False, methods=["get"])
    def today(self, request):
        today = timezone.now().date()
        rows = self.queryset.filter(date=today).order_by("machine__code")
        agg = rows.aggregate(
            target=Sum("target_bph"),
            actual=Sum("actual_bph"),
            variance=Sum("variance"),
        )
        return Response({
            "date": str(today),
            "totals": agg,
            "rows": ProductionPlanSerializer(rows, many=True).data,
        })

    @action(detail=False, methods=["get"])
    def variance_report(self, request):
        days = int(request.query_params.get("days", 7))
        start = timezone.now().date() - timedelta(days=days)
        rows = self.queryset.filter(date__gte=start).order_by("-date", "machine__code")
        out = [
            {
                "date": f"{r.date:%Y-%m-%d}",
                "machine": r.machine_id,
                "machine_code": r.machine.code,
                "product": r.product,
                "target": r.target_bph,
                "actual": r.actual_bph,
                "variance": r.variance,
                "variance_pct": r.variance_pct,
            }
            for r in rows
        ]
        return Response({"window_days": days, "rows": out})


@extend_schema(tags=["Planning"])
class PlanningOrderViewSet(viewsets.ModelViewSet):
    queryset = PlanningOrder.objects.select_related("machine", "mold", "bottle", "created_by")
    serializer_class = PlanningOrderSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("machine", "status", "mold")
    search_fields = ("product_reference", "color", "notes")
    ordering = ["machine", "priority", "id"]

    def perform_create(self, serializer):
        if self.request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour créer une commande de planning.")
        obj = serializer.save(created_by=self.request.user)
        log_activity(self.request.user, "planning_order.created", "PlanningOrder", obj.pk, f"{obj.product_reference} × {obj.quantity}")

    def perform_update(self, serializer):
        if self.request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour modifier une commande de planning.")
        obj = serializer.save()
        log_activity(self.request.user, "planning_order.updated", "PlanningOrder", obj.pk, f"{obj.product_reference} × {obj.quantity}")

    def perform_destroy(self, instance):
        if self.request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour supprimer une commande de planning.")
        if instance.status == PlanningOrderStatus.DONE:
            raise PermissionDenied("Impossible de supprimer une commande terminée — c'est un enregistrement historique.")
        detail = f"{instance.product_reference} × {instance.quantity}"
        pk = instance.pk
        instance.delete()
        log_activity(self.request.user, "planning_order.deleted", "PlanningOrder", pk, detail)

    @action(detail=False, methods=["get"])
    def schedule(self, request):
        """Computed sequence + timing for the order queue (plan.md §7's
        automatic calculations) — never stored, always recomputed on read."""
        machine_id = request.query_params.get("machine")
        machine = Machine.objects.filter(pk=machine_id).first() if machine_id else None
        return Response(calculate_schedule(machine=machine))
