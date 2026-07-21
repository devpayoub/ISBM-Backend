from rest_framework import serializers

from .models import ProductionPlan


class ProductionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionPlan
        fields = (
            "id", "date", "machine", "product",
            "target_bph", "actual_bph", "variance", "variance_pct",
            "notes", "created_at", "updated_at",
        )
        read_only_fields = ("id", "variance", "variance_pct", "created_at", "updated_at")
