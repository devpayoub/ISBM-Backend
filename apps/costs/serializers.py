from rest_framework import serializers

from .models import CostParameter, CostRecord


class CostParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CostParameter
        fields = ("id", "name", "label", "value", "unit", "is_active", "effective_from",
                  "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class CostRecordSerializer(serializers.ModelSerializer):
    machine_code = serializers.CharField(source="machine.code", read_only=True)

    class Meta:
        model = CostRecord
        fields = ("id", "machine", "machine_code", "date", "shift",
                  "labor_cost", "total_cost",
                  "production_count", "cost_per_bottle", "computed_at")
        read_only_fields = ("id", "computed_at", "total_cost", "cost_per_bottle")
