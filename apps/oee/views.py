from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions import IsAdminOrManagerOrReadOnly
from apps.machines.models import Machine, Parameter
from apps.production.models import ProductionEntry

from .models import OEERecord
from .serializers import OEERecalcSerializer, OEERecordSerializer


def _shift_duration_param() -> Decimal:
    try:
        return Decimal(str(Parameter.objects.get(key="SHIFT_DURATION_MIN", is_active=True).value))
    except Parameter.DoesNotExist:
        return Decimal(1440)


class OEEViewSet(viewsets.ModelViewSet):
    queryset = OEERecord.objects.select_related("machine").all()
    serializer_class = OEERecordSerializer
    permission_classes = (IsAuthenticated, IsAdminOrManagerOrReadOnly)
    filterset_fields = ("machine", "date", "shift")
    ordering_fields = ("date", "trs_pct")
    ordering = ["-date", "machine__code"]

    def perform_create(self, serializer):
        rec = serializer.save()
        rec.compute()
        rec.save()
        return rec

    def perform_update(self, serializer):
        rec = serializer.save()
        rec.compute()
        rec.save()

    @action(detail=False, methods=["get"])
    def current(self, request):
        today = timezone.now().date()
        rows = self.queryset.filter(date=today).order_by("machine__code")
        return Response(OEERecordSerializer(rows, many=True).data)

    @action(detail=True, methods=["get"])
    def detail(self, request, pk=None):
        rec = self.get_object()
        return Response(OEERecordSerializer(rec).data)

    @action(detail=False, methods=["get"], url_path=r"by-machine/(?P<machine_id>\d+)")
    def detail_by_machine(self, request, machine_id=None):
        machine = get_object_or_404(Machine, pk=machine_id)
        rows = self.queryset.filter(machine=machine)[:30]
        return Response(OEERecordSerializer(rows, many=True).data)

    @action(detail=False, methods=["get"])
    def trends(self, request):
        days = int(request.query_params.get("days", 30))
        start = timezone.now().date() - timedelta(days=days)
        rows = self.queryset.filter(date__gte=start).order_by("date", "machine__code")
        return Response(OEERecordSerializer(rows, many=True).data)

    @action(detail=False, methods=["post"])
    def recalc(self, request):
        """Rebuild OEERecord rows from ProductionEntry for a given date."""
        ser = OEERecalcSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        date = ser.validated_data["date"]
        machine_id = ser.validated_data.get("machine_id")

        machines = Machine.objects.filter(is_active=True)
        if machine_id:
            machines = machines.filter(pk=machine_id)

        shift_duration = _shift_duration_param()
        count = 0
        for m in machines:
            entries = ProductionEntry.objects.filter(date=date, machine=m)
            if not entries.exists():
                continue
            agg = entries.aggregate(
                bottles=Sum("bottles_produced"),
                caps=Sum("caps_produced"),
                rejects=Sum("reject_count"),
                downtime=Sum("downtime_min"),
                pet=Sum("pet_kg"), energy=Sum("energy_kwh"), air=Sum("air_m3"),
            )
            actual = (agg["bottles"] or 0) + (agg["caps"] or 0)
            nominal = m.nominal_bph or m.nominal_cph or 0
            theo = int(nominal * float(shift_duration) / 60)  # bph * hours
            rec, _ = OEERecord.objects.update_or_create(
                machine=m, date=date, shift="DAY",
                defaults={
                    "actual_production": actual,
                    "theoretical_production": theo,
                    "total_downtime_min": agg["downtime"] or 0,
                    "reject_count": agg["rejects"] or 0,
                    "shift_duration_min": int(shift_duration),
                    "kwh_per_bottle": Decimal(agg["energy"] or 0) / Decimal(actual or 1),
                    "air_per_bottle": Decimal(agg["air"] or 0) / Decimal(actual or 1),
                    "pet_per_bottle": Decimal(agg["pet"] or 0) / Decimal(actual or 1),
                },
            )
            rec.compute()
            rec.save()
            count += 1
        return Response({"date": str(date), "rows_recomputed": count})
