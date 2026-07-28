from rest_framework import serializers

from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True, default="Système")
    user_email = serializers.CharField(source="user.email", read_only=True, default="")
    user_role = serializers.CharField(source="user.role", read_only=True, default="")

    class Meta:
        model = ActivityLog
        fields = (
            "id", "user", "user_name", "user_email", "user_role",
            "action", "target_type", "target_id", "detail", "created_at",
        )
        read_only_fields = fields
