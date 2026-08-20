from rest_framework import serializers

from .models import (
    ChecklistItem, ChecklistSection, ChecklistTemplate, Intervention,
    MaintenanceControl, MaintenanceControlResult, PreventiveMaintenance,
)


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


# ─────────────────────── Controller "Control" page (plan.md §12) ───────────────────────

class ChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistItem
        fields = ("id", "text", "order")


class ChecklistSectionSerializer(serializers.ModelSerializer):
    items = ChecklistItemSerializer(many=True, read_only=True)

    class Meta:
        model = ChecklistSection
        fields = ("id", "name", "order", "items")


class ChecklistTemplateSerializer(serializers.ModelSerializer):
    sections = ChecklistSectionSerializer(many=True, read_only=True)

    class Meta:
        model = ChecklistTemplate
        fields = ("id", "key", "name", "is_active", "sections")


class MaintenanceControlResultSerializer(serializers.ModelSerializer):
    item_text = serializers.CharField(source="item.text", read_only=True)
    section_name = serializers.CharField(source="item.section.name", read_only=True)

    class Meta:
        model = MaintenanceControlResult
        fields = ("id", "item", "item_text", "section_name", "status", "note")
        read_only_fields = ("id", "item", "item_text", "section_name")


class MaintenanceControlSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)
    machine_code = serializers.CharField(source="machine.code", read_only=True, default="")
    equipment_name = serializers.CharField(source="equipment.name", read_only=True, default="")
    target_label = serializers.CharField(read_only=True)
    controller_name = serializers.CharField(source="controller.full_name", read_only=True, default="")
    confirmed_by_name = serializers.CharField(source="confirmed_by.full_name", read_only=True, default="")
    is_locked = serializers.BooleanField(read_only=True)
    results = MaintenanceControlResultSerializer(many=True, read_only=True)

    class Meta:
        model = MaintenanceControl
        fields = (
            "id", "template", "template_name", "machine", "machine_code",
            "equipment", "equipment_name", "target_label", "date", "shift",
            "controller", "controller_name", "confirmed_at", "confirmed_by",
            "confirmed_by_name", "is_locked", "created_at", "updated_at", "results",
        )
        read_only_fields = (
            "id", "template", "template_name", "machine", "machine_code",
            "equipment", "equipment_name", "target_label", "controller",
            "controller_name", "confirmed_at", "confirmed_by", "confirmed_by_name",
            "is_locked", "created_at", "updated_at", "results",
        )


class MaintenanceControlStartSerializer(serializers.Serializer):
    machine = serializers.IntegerField(required=False, allow_null=True)
    equipment = serializers.IntegerField(required=False, allow_null=True)
    date = serializers.DateField()
    shift = serializers.ChoiceField(choices=MaintenanceControl._meta.get_field("shift").choices)

    def validate(self, attrs):
        if bool(attrs.get("machine")) == bool(attrs.get("equipment")):
            raise serializers.ValidationError("Fournir exactement un parmi machine/equipment.")
        return attrs


class MaintenanceControlResultInputSerializer(serializers.Serializer):
    item = serializers.IntegerField()
    status = serializers.ChoiceField(choices=MaintenanceControlResult._meta.get_field("status").choices)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class MaintenanceControlSubmitResultsSerializer(serializers.Serializer):
    results = MaintenanceControlResultInputSerializer(many=True)
