from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import log_activity
from apps.machines.models import Machine
from apps.stock.services import sync_reservations_for_order

from .models import PlanningOrder, PlanningOrderStatus
from .serializers import PlanningOrderSerializer
from .services import calculate_schedule

# plan.md §2: Admin "creates/manages planning inputs and priorities" — not
# a Controller/Operator capability.
MANAGE_ROLES = ("ADMIN", "MANAGER")


@extend_schema(tags=["Planning"])
class PlanningOrderViewSet(viewsets.ModelViewSet):
    queryset = PlanningOrder.objects.select_related("machine", "mold", "bottle", "created_by")
    serializer_class = PlanningOrderSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("machine", "status", "mold")
    search_fields = ("product_reference", "color", "notes")
    ordering = ["machine", "requested_start", "id"]

    def perform_create(self, serializer):
        if self.request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour créer une commande de planning.")
        obj = serializer.save(created_by=self.request.user)
        sync_reservations_for_order(obj)
        log_activity(self.request.user, "planning_order.created", "PlanningOrder", obj.pk, f"{obj.product_reference} × {obj.quantity}")

    def perform_update(self, serializer):
        if self.request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour modifier une commande de planning.")
        obj = serializer.save()
        sync_reservations_for_order(obj)
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
