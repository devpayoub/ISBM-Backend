from django.db.models import F
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import log_activity

from .models import StockItem
from .serializers import StockItemSerializer, StockMoveSerializer
from .services import apply_movement

# plan.md §4: stock is an Admin capability — Controller/Maintenance/Operator
# read only (Reclamation and Package traceability, phases 6/9, need read
# access to stock references).
MANAGE_ROLES = ("ADMIN", "MANAGER")


@extend_schema(tags=["Stock"])
class StockItemViewSet(viewsets.ModelViewSet):
    queryset = StockItem.objects.select_related("created_by").prefetch_related("movements__created_by")
    serializer_class = StockItemSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("type", "is_active")
    search_fields = ("name", "reference", "supplier", "batch")
    ordering_fields = ("name", "quantity", "type")
    ordering = ["type", "name"]

    def perform_create(self, serializer):
        if self.request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour créer un article de stock.")
        item = serializer.save(created_by=self.request.user)
        log_activity(self.request.user, "stock_item.created", "StockItem", item.pk, f"{item.name} ({item.reference})")

    def perform_update(self, serializer):
        if self.request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour modifier un article de stock.")
        item = serializer.save()
        log_activity(self.request.user, "stock_item.updated", "StockItem", item.pk, f"{item.name} ({item.reference})")

    def perform_destroy(self, instance):
        if self.request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour archiver un article de stock.")
        # Soft-delete: movement history must survive (plan.md §15 — don't
        # delete records required for historical traceability).
        detail = f"{instance.name} ({instance.reference})"
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        log_activity(self.request.user, "stock_item.archived", "StockItem", instance.pk, detail)

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        if request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour enregistrer un mouvement de stock.")
        item = self.get_object()
        ser = StockMoveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        quantity_before = item.quantity
        apply_movement(item, data["type"], data["delta"], data.get("reason", ""), request.user)
        log_activity(
            request.user, "stock_item.movement", "StockItem", item.pk,
            f"{item.name}: {data['type']} {data['delta']} ({quantity_before} → {item.quantity})",
        )
        item.refresh_from_db()
        return Response(StockItemSerializer(item).data)

    @action(detail=False, methods=["get"], url_path="low-stock")
    def low_stock(self, request):
        rows = self.get_queryset().filter(is_active=True, quantity__lte=F("min_threshold"))
        return Response(StockItemSerializer(rows, many=True).data)
