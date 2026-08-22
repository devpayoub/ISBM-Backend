from rest_framework import serializers

from apps.machines.models import Machine
from apps.stock.services import raw_and_colorant_requirement

from .models import ProductionEntry, ProductionEntryStatus, Shift


class ProductionEntrySerializer(serializers.ModelSerializer):
    machine_code = serializers.CharField(source="machine.code", read_only=True)
    shift = serializers.ChoiceField(choices=Shift.choices, required=False)
    planning_order_reference = serializers.CharField(source="planning_order.product_reference", read_only=True, default="")
    validated_by_name = serializers.CharField(source="validated_by.full_name", read_only=True, default="")
    # Read-only preview of what validating THIS entry as-is would consume —
    # lets the frontend show theoretical-vs-actual before "Valider" is
    # clicked, without a separate dry-run endpoint. None once there's
    # nothing to preview (no linked order/recipe, or nothing produced yet).
    theoretical_raw_kg = serializers.SerializerMethodField()
    theoretical_colorant_kg = serializers.SerializerMethodField()

    class Meta:
        model = ProductionEntry
        fields = (
            "id", "date", "hour", "machine", "machine_code", "shift",
            "planning_order", "planning_order_reference",
            "bottles_produced", "caps_produced", "reject_count", "reject_pct",
            "downtime_min", "downtime_reason",
            "pet_kg", "energy_kwh", "air_m3",
            "status", "validated_at", "validated_by", "validated_by_name",
            "raw_material_consumed_kg", "colorant_consumed_kg",
            "theoretical_raw_kg", "theoretical_colorant_kg",
            "recorded_by", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "recorded_by", "shift", "status", "validated_at", "validated_by", "validated_by_name",
            "raw_material_consumed_kg", "colorant_consumed_kg", "created_at", "updated_at",
        )

    def _requirement(self, obj):
        if not obj.planning_order or not obj.planning_order.bottle or not obj.bottles_produced:
            return None
        return raw_and_colorant_requirement(obj.planning_order.bottle, obj.bottles_produced)

    def get_theoretical_raw_kg(self, obj):
        req = self._requirement(obj)
        return str(req[1]) if req else None

    def get_theoretical_colorant_kg(self, obj):
        req = self._requirement(obj)
        return str(req[3]) if req and req[3] is not None else None


class ProductionBulkSerializer(serializers.Serializer):
    entries = ProductionEntrySerializer(many=True)

    def create(self, validated):
        user = self.context["request"].user
        results = []
        for item in validated["entries"]:
            date = item.pop("date")
            hour = item.pop("hour")
            machine = item.pop("machine")
            existing = ProductionEntry.objects.filter(date=date, hour=hour, machine=machine).first()
            if existing and existing.status != ProductionEntryStatus.DRAFT:
                # Locked by a prior validation — the fast grid-save path
                # must never silently overwrite it (that would undo the
                # "validated numbers are final" guarantee). Leave as-is.
                results.append(existing)
                continue
            obj, _ = ProductionEntry.objects.update_or_create(
                date=date, hour=hour, machine=machine,
                defaults={**item, "recorded_by": user},
            )
            results.append(obj)
        return results
