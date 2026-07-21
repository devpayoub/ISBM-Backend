from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions import IsAdminOrManagerOrReadOnly

from .models import ProductionPlan
from .serializers import ProductionPlanSerializer


class ProductionPlanViewSet(viewsets.ModelViewSet):
    queryset = ProductionPlan.objects.select_related("machine").all()
    serializer_class = ProductionPlanSerializer
    permission_classes = (IsAuthenticated, IsAdminOrManagerOrReadOnly)
    filterset_fields = ("date", "machine", "product")
    search_fields = ("product", "notes")
    ordering = ["-date", "machine__code"]

    @action(detail=False, methods=["get"])
    def today(self, request):
        today = timezone.now().date()
        rows = self.queryset.filter(date=today).order_by("machine__code")
        agg = rows.aggregate(
            target=Sum("target_bph"),
            actual=Sum("actual_bph"),
            variance=Sum("variance"),
        )
        return Response({
            "date": str(today),
            "totals": agg,
            "rows": ProductionPlanSerializer(rows, many=True).data,
        })

    @action(detail=False, methods=["get"])
    def variance_report(self, request):
        days = int(request.query_params.get("days", 7))
        start = timezone.now().date() - timedelta(days=days)
        rows = self.queryset.filter(date__gte=start).order_by("-date", "machine__code")
        out = [
            {
                "date": f"{r.date:%Y-%m-%d}",
                "machine": r.machine_id,
                "machine_code": r.machine.code,
                "product": r.product,
                "target": r.target_bph,
                "actual": r.actual_bph,
                "variance": r.variance,
                "variance_pct": r.variance_pct,
            }
            for r in rows
        ]
        return Response({"window_days": days, "rows": out})
