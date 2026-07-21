from collections import defaultdict
from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions import IsAdmin, IsAdminOrManager, IsMaintenance

from .models import Intervention
from .serializers import InterventionFinishSerializer, InterventionSerializer


class InterventionViewSet(viewsets.ModelViewSet):
    queryset = Intervention.objects.select_related("alert", "technician")
    serializer_class = InterventionSerializer
    permission_classes = (IsAuthenticated, IsAdmin | IsMaintenance | IsAdminOrManager)
    filterset_fields = ("technician", "alert__machine")
    search_fields = ("action_taken", "parts_used")
    ordering = ["-started_at"]

    def perform_create(self, serializer):
        if self.request.user.role not in ("ADMIN", "MANAGER", "MAINTENANCE"):
            raise ValidationError("Rôle insuffisant pour créer une intervention.")
        serializer.save(
            technician=self.request.user if self.request.user.role == "MAINTENANCE" else serializer.validated_data.get("technician"),
        )

    @action(detail=True, methods=["patch"])
    def finish(self, request, pk=None):
        iv = self.get_object()
        if iv.finished_at:
            raise ValidationError("Intervention déjà terminée.")
        ser = InterventionFinishSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        iv.finished_at = timezone.now()
        for k in ("action_taken", "parts_used", "notes"):
            if ser.validated_data.get(k) is not None:
                setattr(iv, k, ser.validated_data[k])
        iv.save()
        return Response(InterventionSerializer(iv).data)

    @action(detail=False, methods=["get"])
    def my_tasks(self, request):
        rows = self.queryset.filter(technician=request.user, finished_at__isnull=True)
        return Response(InterventionSerializer(rows, many=True).data)

    @action(detail=False, methods=["get"])
    def mttr(self, request):
        days = int(request.query_params.get("days", 30))
        start = timezone.now() - timedelta(days=days)
        closed = Intervention.objects.filter(finished_at__isnull=False, started_at__gte=start)
        per_machine = closed.values("alert__machine__code").annotate(
            count=Count("id"), avg=Avg("duration_min"),
        )
        out = [
            {
                "machine_code": row["alert__machine__code"],
                "interventions": row["count"],
                "mttr_min": round(row["avg"], 1) if row["avg"] else 0,
            }
            for row in per_machine
        ]
        avg_all = closed.aggregate(avg=Avg("duration_min")).get("avg") or 0
        return Response({"window_days": days, "mttr_global_min": round(avg_all, 1), "rows": out})
