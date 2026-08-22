from rest_framework import serializers

from .models import PlanningOrder, ProductionPlan


class ProductionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionPlan
        fields = (
            "id", "date", "machine", "product",
            "target_bph", "actual_bph", "variance", "variance_pct",
            "notes", "created_at", "updated_at",
        )
        read_only_fields = ("id", "variance", "variance_pct", "created_at", "updated_at")


class PlanningOrderSerializer(serializers.ModelSerializer):
    machine_code = serializers.CharField(source="machine.code", read_only=True, default="")
    mold_name = serializers.CharField(source="mold.name", read_only=True, default="")
    mold_reference = serializers.CharField(source="mold.reference", read_only=True, default="")
    bottle_category = serializers.CharField(source="bottle.category", read_only=True, default="")
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default="")

    class Meta:
        model = PlanningOrder
        fields = (
            "id", "machine", "machine_code", "mold", "mold_name", "mold_reference",
            "bottle", "bottle_category", "product_reference", "color", "color_formulation",
            "quantity", "time_per_bottle_sec", "mold_change_min", "priority",
            "requested_start", "status", "notes",
            "created_by", "created_by_name", "created_at", "updated_at",
        )
        read_only_fields = ("id", "product_reference", "status", "created_by", "created_by_name", "created_at", "updated_at")

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("La quantité doit être positive.")
        return value

    def validate_time_per_bottle_sec(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le temps par bouteille doit être positif.")
        return value
