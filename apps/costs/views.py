from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions import IsAdmin, IsAdminOrManagerOrReadOnly
from apps.machines.models import Machine
from apps.production.models import ProductionEntry

from .models import CostParameter, CostRecord
from .serializers import CostParameterSerializer, CostRecordSerializer


def _param(name: str) -> Decimal:
    try:
        return Decimal(str(CostParameter.objects.get(name=name, is_active=True).value))
    except CostParameter.DoesNotExist:
        return Decimal(0)


@extend_schema(tags=["Costs"])
class CostParameterViewSet(viewsets.ModelViewSet):
    queryset = CostParameter.objects.all()
    serializer_class = CostParameterSerializer
    permission_classes = (IsAuthenticated, IsAdminOrManagerOrReadOnly)
    filterset_fields = ("is_active",)
    search_fields = ("name", "label")
    ordering = ["name"]

    @action(detail=False, methods=["get"])
    def active(self, request):
        rows = self.queryset.filter(is_active=True)
        return Response(CostParameterSerializer(rows, many=True).data)

    def bulk_update(self, request):
        """PUT on the collection: update ``value`` for a batch of parameters at once."""
        if not isinstance(request.data, list):
            raise ValidationError("Une liste de paramètres est attendue.")
        by_id = {p.id: p for p in self.queryset.filter(id__in=[item.get("id") for item in request.data])}
        updated = []
        for item in request.data:
            param = by_id.get(item.get("id"))
            if param is None or "value" not in item:
                continue
            param.value = item["value"]
            param.save(update_fields=["value"])
            updated.append(param)
        return Response(CostParameterSerializer(updated, many=True).data)


@extend_schema(tags=["Costs"])
class CostRecordViewSet(viewsets.ModelViewSet):
    queryset = CostRecord.objects.select_related("machine").all()
    serializer_class = CostRecordSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("machine", "date", "shift")
    ordering = ["-date", "machine__code"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "recalc"):
            return (IsAuthenticated(), IsAdmin())
        return (IsAuthenticated(),)

    def perform_create(self, serializer):
        rec = serializer.save()
        rec.compute_totals()
        rec.save()

    def perform_update(self, serializer):
        rec = serializer.save()
        rec.compute_totals()
        rec.save()

    @action(detail=False, methods=["get"])
    def daily(self, request):
        date_str = request.query_params.get("date") or timezone.now().date()
        rows = self.queryset.filter(date=date_str)
        agg = rows.aggregate(
            labor=Sum("labor_cost"), total=Sum("total_cost"),
            production=Sum("production_count"),
        )
        return Response({"date": str(date_str), "totals": agg, "rows": CostRecordSerializer(rows, many=True).data})

    @action(detail=False, methods=["get"])
    def monthly_report(self, request):
        today = timezone.now().date()
        start = today.replace(day=1)
        rows = self.queryset.filter(date__gte=start, date__lte=today)
        agg = rows.aggregate(
            labor=Sum("labor_cost"), total=Sum("total_cost"), production=Sum("production_count"),
        )
        per_machine = rows.values("machine__code").annotate(total=Sum("total_cost"), prod=Sum("production_count"))
        return Response({"month": str(today), "totals": agg, "per_machine": list(per_machine)})

    @action(detail=False, methods=["post"])
    def recalc(self, request):
        from datetime import date as dcls
        d = request.data.get("date")
        try:
            date_val = dcls.fromisoformat(d) if d else timezone.now().date()
        except ValueError:
            return Response({"detail": "date invalide"}, status=400)

        labor_rate = _param("COST_LABOR_H")
        count = 0
        for m in Machine.objects.filter(is_active=True):
            ents = ProductionEntry.objects.filter(date=date_val, machine=m)
            if not ents.exists():
                continue
            agg = ents.aggregate(bottles=Sum("bottles_produced"), caps=Sum("caps_produced"))
            prod = (agg["bottles"] or 0) + (agg["caps"] or 0) or 1
            labor_cost = Decimal(24) * labor_rate  # full 24h shift
            rec, _ = CostRecord.objects.update_or_create(
                machine=m, date=date_val, shift="DAY",
                defaults={"labor_cost": labor_cost, "production_count": prod},
            )
            rec.compute_totals()
            rec.save()
            count += 1
        return Response({"date": str(date_val), "rows": count})
