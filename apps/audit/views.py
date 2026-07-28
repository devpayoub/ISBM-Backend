from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.common.permissions import IsAdmin

from .models import ActivityLog
from .serializers import ActivityLogSerializer


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ActivityLog.objects.select_related("user")
    serializer_class = ActivityLogSerializer
    permission_classes = (IsAuthenticated, IsAdmin)
    filterset_fields = ("user", "action")
    search_fields = ("action", "detail", "user__email", "user__first_name", "user__last_name")
    ordering = ["-created_at"]
