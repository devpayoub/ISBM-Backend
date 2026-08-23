from rest_framework import serializers

from .models import Reclamation, ReclamationAttachment


class ReclamationAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True, default="")

    class Meta:
        model = ReclamationAttachment
        fields = ("id", "reclamation", "file", "uploaded_by", "uploaded_by_name", "uploaded_at")
        read_only_fields = ("id", "reclamation", "uploaded_by", "uploaded_by_name", "uploaded_at")


class ReclamationSerializer(serializers.ModelSerializer):
    stock_item_name = serializers.CharField(source="stock_item.name", read_only=True, default="")
    stock_item_reference = serializers.CharField(source="stock_item.reference", read_only=True, default="")
    package_reference = serializers.CharField(source="package.reference", read_only=True, default="")
    machine_code = serializers.CharField(source="machine.code", read_only=True, default="")
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default="")
    closed_by_name = serializers.CharField(source="closed_by.full_name", read_only=True, default="")
    attachments = ReclamationAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Reclamation
        fields = (
            "id", "reference", "client", "reported_at", "description",
            "stock_item", "stock_item_name", "stock_item_reference",
            "product_reference", "package", "package_reference",
            "machine", "machine_code", "production_at",
            "severity", "status", "resolved_personnel", "resolution",
            "created_by", "created_by_name", "closed_by", "closed_by_name", "closed_at",
            "attachments", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "reference", "status", "machine", "machine_code",
            "production_at", "resolved_personnel",
            "created_by", "created_by_name", "closed_by", "closed_by_name", "closed_at",
            "attachments", "created_at", "updated_at",
        )


class ReclamationCloseSerializer(serializers.Serializer):
    resolution = serializers.CharField()
