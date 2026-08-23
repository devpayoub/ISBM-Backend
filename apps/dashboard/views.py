from datetime import timedelta

from django.db.models import Count, F, Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
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


@extend_schema(tags=["Dashboard"])
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
            "machines_status": mstatus_map,
            "pareto_top5": list(pareto),
            "mttr": mttr_out,
        })


@extend_schema(tags=["Dashboard"])
class MachinesStatusView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        rows = Machine.objects.values("id", "code", "name", "type", "status", "is_active").order_by("code")
        return Response(list(rows))


@extend_schema(tags=["Dashboard"])
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


@extend_schema(tags=["Dashboard"])
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


@extend_schema(tags=["Dashboard"])
class MaterialsOverviewView(APIView):
    """Stock/production aggregate for the dashboard (Phase 6 of the
    material-requirement plan) — reuses every earlier phase's own service
    instead of re-deriving any of the maths: apps.catalog.services.
    max_producible (capacity + limiting component), apps.planning.services.
    calculate_schedule (per-order stock status, Phase 3), apps.stock.
    services.remaining_quantity_for_order (planned-vs-actual, Phase 5)."""
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        from apps.catalog.models import BottleCharacteristic
        from apps.catalog.services import max_producible
        from apps.planning.models import PlanningOrder, PlanningOrderStatus
        from apps.planning.services import calculate_schedule
        from apps.stock.models import StockItem
        from apps.stock.services import remaining_quantity_for_order

        active_items = StockItem.objects.filter(is_active=True)
        near_threshold_qs = active_items.filter(quantity__lte=F("min_threshold")).order_by("quantity")
        near_threshold = [
            {
                "id": i.id, "reference": i.reference, "name": i.name,
                "quantity": str(i.quantity), "unit": i.unit, "status": i.get_status(),
            }
            for i in near_threshold_qs[:10]
        ]

        capacity_rows = []
        bottles = BottleCharacteristic.objects.filter(is_active=True).select_related("raw_material", "colorant")
        for b in bottles:
            cap = max_producible(b)
            capacity_rows.append({
                "id": b.id, "category": b.category,
                "physical_capacity": cap.physical_capacity,
                "available_capacity": cap.available_capacity,
                "limiting_component": cap.limiting_component,
                "limiting_component_name": cap.limiting_component_name,
            })

        # Per-order stock status, straight from Planning's own sequential
        # simulation (Phase 3) — never re-derived here.
        status_counts = {"OK": 0, "WARNING": 0, "INSUFFICIENT": 0}
        for row in calculate_schedule():
            check = row.get("material_check")
            if check:
                status_counts[check["stock_status"]] = status_counts.get(check["stock_status"], 0) + 1

        # Planned-vs-actual: sum each active order's original quantity
        # against how much of it remains unproduced (Phase 5's own
        # remaining_quantity_for_order) — the delta is what's actually been
        # validated/produced so far.
        active_orders = PlanningOrder.objects.filter(
            status__in=(PlanningOrderStatus.QUEUED, PlanningOrderStatus.IN_PROGRESS),
        )
        planned_qty = 0
        remaining_qty = 0
        for order in active_orders:
            planned_qty += order.quantity
            remaining_qty += remaining_quantity_for_order(order)
        actual_qty = planned_qty - remaining_qty

        return Response({
            "stock": {
                "total_active_items": active_items.count(),
                "near_threshold_count": near_threshold_qs.count(),
                "near_threshold": near_threshold,
            },
            "capacity": capacity_rows,
            "orders": {
                "queued": PlanningOrder.objects.filter(status=PlanningOrderStatus.QUEUED).count(),
                "in_progress": PlanningOrder.objects.filter(status=PlanningOrderStatus.IN_PROGRESS).count(),
                "stock_ok": status_counts["OK"],
                "stock_warning": status_counts["WARNING"],
                "stock_insufficient": status_counts["INSUFFICIENT"],
            },
            "production": {
                "planned_quantity": planned_qty,
                "actual_quantity": actual_qty,
                "completion_pct": round((actual_qty / planned_qty) * 100, 1) if planned_qty else 0,
            },
        })
