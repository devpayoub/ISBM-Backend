from rest_framework import serializers

from apps.machines.models import Machine

from .models import ProductionEntry, Shift


class ProductionEntrySerializer(serializers.ModelSerializer):
    machine_code = serializers.CharField(source="machine.code", read_only=True)
    shift = serializers.ChoiceField(choices=Shift.choices, required=False)

    class Meta:
        model = ProductionEntry
        fields = (
            "id", "date", "hour", "machine", "machine_code", "shift",
            "bottles_produced", "caps_produced", "reject_count", "reject_pct",
            "downtime_min", "downtime_reason",
            "pet_kg", "energy_kwh", "air_m3",
            "recorded_by", "created_at", "updated_at",
        )
        read_only_fields = ("id", "recorded_by", "shift", "created_at", "updated_at")


class ProductionBulkSerializer(serializers.Serializer):
    entries = ProductionEntrySerializer(many=True)

    def create(self, validated):
        user = self.context["request"].user
        results = []
        for item in validated["entries"]:
            date = item.pop("date")
            hour = item.pop("hour")
            machine = item.pop("machine")
            obj, _ = ProductionEntry.objects.update_or_create(
                date=date, hour=hour, machine=machine,
                defaults={**item, "recorded_by": user},
            )
            results.append(obj)
        return results
