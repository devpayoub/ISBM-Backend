from rest_framework import serializers

from .models import StockItem, StockMovement


class StockMovementSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default="")

    class Meta:
        model = StockMovement
        fields = (
            "id", "stock_item", "type", "delta", "quantity_before", "quantity_after",
            "reason", "created_by", "created_by_name", "created_at",
        )
        read_only_fields = fields


class StockItemSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default="")
    movements = StockMovementSerializer(many=True, read_only=True)

    class Meta:
        model = StockItem
        fields = (
            "id", "type", "name", "reference", "supplier", "ral", "unit",
            "quantity", "min_threshold", "batch", "received_at", "notes",
            "is_active", "status", "created_by", "created_by_name",
            "movements", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "quantity", "status", "created_by", "created_by_name",
            "movements", "created_at", "updated_at",
        )

    def get_status(self, obj):
        return obj.get_status()


class StockMoveSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["RECEIPT", "CONSUMPTION", "ADJUSTMENT"])
    delta = serializers.DecimalField(max_digits=12, decimal_places=3)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=300)

    def validate_delta(self, value):
        if value == 0:
            raise serializers.ValidationError("La quantité ne peut pas être nulle.")
        return value

    def validate(self, attrs):
        # RECEIPT only ever adds, CONSUMPTION only ever removes — ADJUSTMENT
        # is the one type allowed to correct a stock count in either
        # direction (e.g. after a physical recount).
        if attrs["type"] == "RECEIPT" and attrs["delta"] < 0:
            raise serializers.ValidationError("Une réception doit avoir une quantité positive.")
        if attrs["type"] == "CONSUMPTION" and attrs["delta"] > 0:
            raise serializers.ValidationError("Une consommation doit avoir une quantité négative.")
        return attrs
