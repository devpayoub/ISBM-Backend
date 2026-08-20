from rest_framework import serializers

from .models import BottleCharacteristic


class BottleCharacteristicSerializer(serializers.ModelSerializer):
    raw_material_name = serializers.CharField(source="raw_material.name", read_only=True, default="")
    raw_material_reference = serializers.CharField(source="raw_material.reference", read_only=True, default="")
    colorant_name = serializers.CharField(source="colorant.name", read_only=True, default="")
    colorant_reference = serializers.CharField(source="colorant.reference", read_only=True, default="")

    class Meta:
        model = BottleCharacteristic
        fields = (
            "id", "category", "reference",
            "raw_material", "raw_material_name", "raw_material_reference", "raw_material_qty_g",
            "colorant", "colorant_name", "colorant_reference", "colorant_qty_g",
            "bouchant_type", "bouchant_raw_material_qty_g", "bouchant_colorant_qty_g",
            "is_active", "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
