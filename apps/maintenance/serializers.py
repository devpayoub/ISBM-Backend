from rest_framework import serializers

from .models import Intervention, PreventiveMaintenance


class InterventionSerializer(serializers.ModelSerializer):
    alert_title = serializers.CharField(source="alert.title", read_only=True, default="")
    machine_name = serializers.CharField(source="alert.machine.name", read_only=True, default="")
    technician_name = serializers.CharField(source="technician.full_name", read_only=True, default="")
    reported_by_name = serializers.CharField(source="alert.reported_by.full_name", read_only=True, default="")

    class Meta:
        model = Intervention
        fields = (
            "id", "alert", "alert_title", "machine_name",
            "technician", "technician_name", "reported_by_name",
            "action_taken", "parts_used",
            "notes", "started_at", "finished_at", "duration_min", "verified",
        )
        read_only_fields = ("id", "duration_min", "verified")


class InterventionFinishSerializer(serializers.Serializer):
    action_taken = serializers.CharField(required=False, allow_blank=True)
    parts_used = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class PreventiveMaintenanceSerializer(serializers.ModelSerializer):
    machine_name = serializers.CharField(source="machine.name", read_only=True, default="")
    assigned_to_name = serializers.CharField(source="assigned_to.full_name", read_only=True, default="")

    class Meta:
        model = PreventiveMaintenance
        fields = (
            "id", "machine", "machine_name", "task", "frequency", "checklist",
            "last_done", "next_due", "assigned_to", "assigned_to_name", "status",
        )
        read_only_fields = ("id",)
