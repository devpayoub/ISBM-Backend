from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.machines.models import Machine
from apps.machines.serializers import MachineSerializer

User = get_user_model()

from .models import (
    SupplierSolution, Ticket, TicketAttachment, TicketClosure, TicketComment,
    TicketStatusLog,
)


class TicketAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True, default="")

    class Meta:
        model = TicketAttachment
        fields = ("id", "ticket", "file", "category", "uploaded_by", "uploaded_by_name", "uploaded_at")
        read_only_fields = ("id", "ticket", "uploaded_by", "uploaded_by_name", "uploaded_at")


class TicketCommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = TicketComment
        fields = ("id", "ticket", "user", "user_name", "text", "created_at")
        read_only_fields = ("id", "ticket", "user", "user_name", "created_at")


class TicketStatusLogSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source="changed_by.full_name", read_only=True, default="")

    class Meta:
        model = TicketStatusLog
        fields = (
            "id", "ticket", "from_status", "to_status", "decision", "reason",
            "changed_by", "changed_by_name", "created_at",
        )
        read_only_fields = fields


class SupplierSolutionSerializer(serializers.ModelSerializer):
    proposed_by_name = serializers.CharField(source="proposed_by.full_name", read_only=True, default="")

    class Meta:
        model = SupplierSolution
        fields = (
            "id", "ticket", "diagnostic", "probable_cause", "root_cause",
            "repair_procedure", "spare_parts", "estimated_duration_min", "urgency",
            "proposed_by", "proposed_by_name", "proposed_at",
        )
        read_only_fields = ("id", "ticket", "proposed_by", "proposed_by_name", "proposed_at")


class TicketClosureSerializer(serializers.ModelSerializer):
    closed_by_name = serializers.CharField(source="closed_by.full_name", read_only=True, default="")

    class Meta:
        model = TicketClosure
        fields = (
            "id", "ticket", "repair_conforms", "restarted_at", "total_downtime_min",
            "intervention_duration_min", "parts_replaced", "intervention_cost",
            "closed_by", "closed_by_name", "closed_at",
        )
        read_only_fields = ("id", "ticket", "closed_by", "closed_by_name", "closed_at")


class TicketSerializer(serializers.ModelSerializer):
    machine_detail = MachineSerializer(source="machine", read_only=True)
    reported_by_name = serializers.CharField(source="reported_by.full_name", read_only=True, default="")
    assigned_supplier_name = serializers.CharField(source="assigned_supplier.full_name", read_only=True, default="")
    attachments = TicketAttachmentSerializer(many=True, read_only=True)
    comments = TicketCommentSerializer(many=True, read_only=True)
    status_logs = TicketStatusLogSerializer(many=True, read_only=True)
    solutions = SupplierSolutionSerializer(many=True, read_only=True)
    closure = TicketClosureSerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = (
            "id", "ticket_number",
            "machine", "machine_detail", "alert", "reported_by", "reported_by_name",
            "assigned_supplier", "assigned_supplier_name",
            "criticality", "status",
            "production_line", "equipment_detail", "error_code",
            "description", "symptoms", "production_impacted",
            "downtime_start", "downtime_end",
            "attachments", "comments", "status_logs", "solutions", "closure",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "ticket_number", "status", "reported_by",
            "assigned_supplier", "assigned_supplier_name",
            "downtime_end",
            "created_at", "updated_at",
        )


class TicketCreateSerializer(serializers.ModelSerializer):
    machine = serializers.PrimaryKeyRelatedField(queryset=Machine.objects.all())
    # Explicitly chosen by whoever declares the ticket — not inferred from
    # which machines a supplier happens to be linked to.
    assigned_supplier = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role="SUPPLIER"),
    )

    class Meta:
        model = Ticket
        fields = (
            "machine", "alert", "criticality", "assigned_supplier",
            "production_line", "equipment_detail", "error_code",
            "description", "symptoms", "production_impacted", "downtime_start",
        )


class TicketValidateSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=[
        "ACCEPTED", "REFUSED", "INFO_REQUESTED", "ONSITE_REQUESTED", "VIDEOCALL_REQUESTED",
    ])
    reason = serializers.CharField(required=False, allow_blank=True)


class TicketCloseSerializer(serializers.Serializer):
    repair_conforms = serializers.BooleanField(default=True)
    restarted_at = serializers.DateTimeField(required=False)
    intervention_duration_min = serializers.IntegerField(required=False)
    parts_replaced = serializers.CharField(required=False, allow_blank=True)
    intervention_cost = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True)
