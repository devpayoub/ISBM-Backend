from rest_framework import serializers

from .models import OEERecord


class OEERecordSerializer(serializers.ModelSerializer):
    machine_code = serializers.CharField(source="machine.code", read_only=True)

    class Meta:
        model = OEERecord
        fields = (
            "id", "machine", "machine_code", "date", "shift",
            "theoretical_production", "actual_production", "total_downtime_min",
            "shift_duration_min", "availability_pct", "performance_pct",
            "quality_pct", "trs_pct",
            "reject_count", "computed_at",
        )
        read_only_fields = ("id", "computed_at", "availability_pct", "performance_pct",
                            "quality_pct", "trs_pct")


class OEERecalcSerializer(serializers.Serializer):
    date = serializers.DateField(required=True)
    machine_id = serializers.IntegerField(required=False)
