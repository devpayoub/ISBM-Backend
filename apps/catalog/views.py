from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import log_activity

from .models import BottleCharacteristic
from .serializers import BottleCharacteristicSerializer
from .services import max_producible, sync_recipe_components

# Same capability shape as Stock (plan.md §10 is an Admin-owned reference
# table; Planning/Package read it later, they don't manage it).
MANAGE_ROLES = ("ADMIN", "MANAGER")


@extend_schema(tags=["Catalog"])
class BottleCharacteristicViewSet(viewsets.ModelViewSet):
    queryset = BottleCharacteristic.objects.select_related("raw_material", "colorant")
    serializer_class = BottleCharacteristicSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("is_active", "bouchant_type")
    search_fields = ("category", "reference")
    ordering = ["category"]

    def perform_create(self, serializer):
        if self.request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour créer une caractéristique bouteille.")
        obj = serializer.save()
        sync_recipe_components(obj)
        log_activity(self.request.user, "bottle_characteristic.created", "BottleCharacteristic", obj.pk, obj.category)

    def perform_update(self, serializer):
        if self.request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour modifier une caractéristique bouteille.")
        obj = serializer.save()
        sync_recipe_components(obj)
        log_activity(self.request.user, "bottle_characteristic.updated", "BottleCharacteristic", obj.pk, obj.category)

    def perform_destroy(self, instance):
        if self.request.user.role not in MANAGE_ROLES:
            raise PermissionDenied("Rôle insuffisant pour archiver une caractéristique bouteille.")
        detail, pk = instance.category, instance.pk
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        log_activity(self.request.user, "bottle_characteristic.archived", "BottleCharacteristic", pk, detail)

    @action(detail=False, methods=["get"])
    def capacity(self, request):
        """"How many bottles we have" answered from current Stock, per
        recipe — never stored, always recomputed on read (same convention
        as Planning's schedule/material_check). max_producible keeps its
        pre-Phase-6 meaning (reservation-aware) so existing consumers don't
        need to change; physical_capacity/limiting_component are additive."""
        rows = self.get_queryset().filter(is_active=True)
        result = []
        for b in rows:
            cap = max_producible(b)
            result.append({
                "id": b.id,
                "category": b.category,
                "raw_material_reference": b.raw_material.reference,
                "raw_material_available_kg": str(b.raw_material.quantity),
                "colorant_reference": b.colorant.reference if b.colorant else "",
                "colorant_available_kg": str(b.colorant.quantity) if b.colorant else None,
                "max_producible": cap.available_capacity,
                "physical_capacity": cap.physical_capacity,
                "limiting_component": cap.limiting_component,
                "limiting_component_name": cap.limiting_component_name,
            })
        return Response(result)
