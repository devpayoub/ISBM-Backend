from rest_framework import serializers

from .models import Intervention


class InterventionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Intervention
        fields = (
            "id", "alert", "technician", "action_taken", "parts_used",
            "notes", "started_at", "finished_at", "duration_min",
        )
        read_only_fields = ("id", "duration_min")


class InterventionFinishSerializer(serializers.Serializer):
    action_taken = serializers.CharField(required=False, allow_blank=True)
    parts_used = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
