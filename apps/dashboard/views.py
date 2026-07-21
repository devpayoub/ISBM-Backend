from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alerts.models import Alert, AlertStatus
from apps.costs.models import CostRecord
from apps.machines.models import Machine, MachineStatus
from apps.oee.models import OEERecord
from apps.production.models import ProductionEntry


def _today():
    return timezone.now().date()


class KPIsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        today = _today()

        # Production totals for the day.
        prod_agg = ProductionEntry.objects.filter(date=today).aggregate(
            bottles=Sum("bottles_produced"),
            caps=Sum("caps_produced"),
            rejects=Sum("reject_count"),
            downtime=Sum("downtime_min"),
            pet=Sum("pet_kg"), energy=Sum("energy_kwh"), air=Sum("air_m3"),
        )

        # TRS / OEE for the day.
        oee_rows = OEERecord.objects.filter(date=today)
        trs_global = oee_rows.values_list("trs_pct", flat=True)
        avg_trs = round(sum(t for t in trs_global) / max(len(list(trs_global)), 1), 2) if oee_rows.exists() else 0

        # Active alerts.
        active_alerts = Alert.objects.filter(
            status__in=["OPEN", "ACKNOWLEDGED", "IN_PROGRESS"],
        ).count()
        critical_active = Alert.objects.filter(
            status__in=["OPEN", "ACKNOWLEDGED", "IN_PROGRESS"], severity="CRITICAL",
        ).count()

        # Cost per bottle today.
        cost_agg = CostRecord.objects.filter(date=today).aggregate(
            total=Sum("total_cost"), prod=Sum("production_count"),
            bottle=Sum("cost_per_bottle"),
        )

        # kWh & air per bottle today.
        total_prod = (prod_agg["bottles"] or 0) + (prod_agg["caps"] or 0) or 1
        kwh_per_bottle = round((prod_agg["energy"] or 0) / total_prod, 4)
        air_per_bottle = round((prod_agg["air"] or 0) / total_prod, 4)

        # Pareto counts today.
        pareto = (
            Alert.objects.values("category__name").annotate(nb=Count("id"))
            .order_by("-nb")[:5]
        )

        # Machines status counts.
        mstatus = (
            Machine.objects.values("status").annotate(nb=Count("id"))
        )
        mstatus_map = {row["status"]: row["nb"] for row in mstatus}

        # MTTR this month.
        from django.db.models import Avg
        last_month = timezone.now() - timedelta(days=30)
        mttr_rows = (
            Alert.objects.filter(
                status=AlertStatus.CLOSED, resolved_at__gte=last_month,
            ).exclude(downtime_min=0).values("machine__code").annotate(avg=Avg("downtime_min"))
        )
        mttr_out = [
            {"machine_code": r["machine__code"], "mttr_min": round(r["avg"], 1)}
            for r in mttr_rows
        ]

        return Response({
            "date": str(today),
            "production": {
                "bottles": prod_agg["bottles"] or 0,
                "caps": prod_agg["caps"] or 0,
                "rejects": prod_agg["rejects"] or 0,
                "downtime_min": prod_agg["downtime"] or 0,
            },
            "trs_global_pct": avg_trs,
            "trs_threshold_pct": 70,
            "active_alerts": active_alerts,
            "critical_active_alerts": critical_active,
            "cost_per_bottle": round(cost_agg["bottle"] or 0, 4),
            "cost_total_today": round(cost_agg["total"] or 0, 2),
            "kwh_per_bottle": kwh_per_bottle,
            "air_per_bottle": air_per_bottle,
            "machines_status": mstatus_map,
            "pareto_top5": list(pareto),
            "mttr": mttr_out,
        })


class MachinesStatusView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        rows = Machine.objects.values("id", "code", "name", "type", "status", "is_active").order_by("code")
        return Response(list(rows))


class ParetoView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        days = int(request.query_params.get("days", 30))
        start = timezone.now() - timedelta(days=days)
        rows = (
            Alert.objects.filter(created_at__gte=start)
            .values("category__name").annotate(nb=Count("id")).order_by("-nb")
        )
        rows = [
            {"cause": r["category__name"] or "(non catégorisée)", "nb": r["nb"]}
            for r in rows
        ]
        return Response({"window_days": days, "rows": rows})


class ShiftReportView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        today = _today()
        per_shift = {}
        for shift in ("MORNING", "AFTERNOON", "NIGHT"):
            agg = ProductionEntry.objects.filter(date=today, shift=shift).aggregate(
                bottles=Sum("bottles_produced"), caps=Sum("caps_produced"),
                downtime=Sum("downtime_min"), rejects=Sum("reject_count"),
            )
            alerts_nb = Alert.objects.filter(created_at__date=today, shift=shift).count()
            per_shift[shift] = {"production": agg, "alerts": alerts_nb}
        return Response({"date": str(today), "shifts": per_shift})
