from rest_framework import serializers

from .models import AuditDocument, NonConformity


class NonConformitySerializer(serializers.ModelSerializer):
    machine_name = serializers.CharField(source="machine.name", read_only=True, default="")
    opened_by_name = serializers.CharField(source="opened_by.full_name", read_only=True, default="")

    class Meta:
        model = NonConformity
        fields = (
            "id", "nc_number", "source", "machine", "machine_name", "product",
            "type", "description", "root_cause", "corrective_action", "preventive_action",
            "status", "opened_by", "opened_by_name", "opened_at", "closed_at", "linked_alert",
        )
        read_only_fields = ("id", "nc_number", "status", "opened_by", "opened_at", "closed_at")


class AuditDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True, default="")

    class Meta:
        model = AuditDocument
        fields = (
            "id", "title", "clause", "file", "version", "status",
            "uploaded_by", "uploaded_by_name", "uploaded_at",
        )
        read_only_fields = ("id", "uploaded_by", "uploaded_at")
