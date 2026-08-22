from rest_framework import serializers

from .models import Package


class PackageSerializer(serializers.ModelSerializer):
    machine_code = serializers.CharField(source="machine.code", read_only=True, default="")
    machine_name = serializers.CharField(source="machine.name", read_only=True, default="")
    bottle_category = serializers.CharField(source="bottle.category", read_only=True, default="")
    raw_material_name = serializers.CharField(source="raw_material.name", read_only=True, default="")
    color_name = serializers.CharField(source="color.name", read_only=True, default="")
    planning_order_reference = serializers.CharField(source="planning_order.product_reference", read_only=True, default="")
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default="")
    verified_by_name = serializers.CharField(source="verified_by.full_name", read_only=True, default="")

    class Meta:
        model = Package
        fields = (
            "id", "reference", "machine", "machine_code", "machine_name",
            "planning_order", "planning_order_reference",
            "bottle", "bottle_category", "bottle_count",
            "raw_material", "raw_material_name", "raw_material_reference_snapshot", "raw_material_consumed_kg",
            "color", "color_name", "color_reference_snapshot", "colorant_consumed_kg",
            "supplier", "production_started_at", "production_finished_at",
            "personnel_snapshot", "notes", "shipped_at", "shipped_to",
            "verified_at", "verified_by", "verified_by_name",
            "created_by", "created_by_name", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "reference",
            "raw_material_reference_snapshot", "raw_material_consumed_kg",
            "color_reference_snapshot", "colorant_consumed_kg",
            "personnel_snapshot", "shipped_at", "shipped_to",
            "verified_at", "verified_by", "verified_by_name",
            "created_by", "created_by_name", "created_at", "updated_at",
        )

    def validate_bottle_count(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le nombre de bouteilles doit être positif.")
        return value

    def validate(self, attrs):
        finished = attrs.get("production_finished_at", getattr(self.instance, "production_finished_at", None))
        started = attrs.get("production_started_at", getattr(self.instance, "production_started_at", None))
        if finished and started and finished < started:
            raise serializers.ValidationError("La date de fin de production ne peut pas être avant le début.")
        return attrs
