from rest_framework import serializers

from apps.machines.models import Machine
from apps.machines.serializers import MachineSerializer

from .models import Alert, AlertCategory, AlertComment, Severity


class AlertCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertCategory
        fields = ("id", "name", "code", "severity_default", "color", "requires_maintenance", "is_active")


class AlertCommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = AlertComment
        fields = ("id", "alert", "user", "user_name", "text", "created_at")
        read_only_fields = ("id", "alert", "user", "user_name", "created_at")


class AlertSerializer(serializers.ModelSerializer):
    machine_detail = MachineSerializer(source="machine", read_only=True)
    machine_name = serializers.CharField(source="machine.name", read_only=True, default="")
    category_detail = AlertCategorySerializer(source="category", read_only=True)
    reported_by_name = serializers.CharField(source="reported_by.full_name", read_only=True)
    acknowledged_by_name = serializers.CharField(source="acknowledged_by.full_name", read_only=True, default="")
    resolved_by_name = serializers.CharField(source="resolved_by.full_name", read_only=True, default="")
    comments_count = serializers.IntegerField(source="comments.count", read_only=True)

    class Meta:
        model = Alert
        fields = (
            "id",
            "machine", "machine_detail", "machine_name",
            "category", "category_detail",
            "title", "description",
            "severity", "status",
            "reported_by", "reported_by_name", "worker_name", "shift",
            "acknowledged_at", "acknowledged_by", "acknowledged_by_name",
            "resolved_at", "resolved_by", "resolved_by_name",
            "closed_at", "escalation_level", "escalated_at",
            "downtime_min", "bottles_lost", "photo", "priority_score",
            "comments_count",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "reported_by", "acknowledged_at", "acknowledged_by",
            "resolved_at", "resolved_by", "closed_at",
            "escalation_level", "escalated_at",
            "priority_score",
            "created_at", "updated_at",
        )


class AlertCreateSerializer(serializers.ModelSerializer):
    machine = serializers.PrimaryKeyRelatedField(queryset=Machine.objects.all())
    title = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Alert
        fields = (
            "machine", "category", "title", "description",
            "severity", "worker_name", "shift",
            "downtime_min", "bottles_lost", "photo",
        )


class AlertActionSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True)
