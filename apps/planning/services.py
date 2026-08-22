from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.catalog.models import RecipeComponentType

from .models import PlanningOrder, PlanningOrderStatus

_RAW_TYPES = (RecipeComponentType.BOTTLE_RAW, RecipeComponentType.CAP_RAW)
_COLORANT_TYPES = (RecipeComponentType.BOTTLE_COLORANT, RecipeComponentType.CAP_COLORANT)


def _order_requirement(order):
    """This order's raw material / colorant requirement (body+cap combined
    per stock_item, same combining rule used everywhere else in this
    codebase) — the per-order building block simulate_stock_sequence()
    walks over. None if the order has no linked bottle recipe."""
    bottle = order.bottle
    if not bottle:
        return None
    components = list(bottle.components.select_related("stock_item").all())
    raw = [c for c in components if c.component_type in _RAW_TYPES]
    colorant = [c for c in components if c.component_type in _COLORANT_TYPES]
    raw_item = raw[0].stock_item if raw else None
    raw_kg = sum((c.qty_per_unit_g for c in raw), Decimal("0")) * order.quantity / Decimal("1000")
    colorant_item = colorant[0].stock_item if colorant else None
    colorant_kg = (
        sum((c.qty_per_unit_g for c in colorant), Decimal("0")) * order.quantity / Decimal("1000")
        if colorant else None
    )
    return {
        "bottle": bottle, "raw_item": raw_item, "raw_kg": raw_kg,
        "colorant_item": colorant_item, "colorant_kg": colorant_kg,
    }


def simulate_stock_sequence(orders_by_start):
    """Walk the FULL order queue — every machine combined, already sorted
    by estimated_start — maintaining one running physical-stock pool per
    material. This is what actually answers "which order first runs out,"
    not just "is total demand too high": apps.stock.services.
    calculate_material_requirements() (Phase 1/2) sums every queued order's
    claim at once, so two orders each individually "fitting" against a
    shared pool can both come back INSUFFICIENT even when the earlier one
    would genuinely succeed. Here, an order whose requirement doesn't fit
    what's left is marked INSUFFICIENT and — critically — does NOT draw
    from the pool, since it presumably won't be produced as scheduled and
    so doesn't block whoever's next in line. Read-only: never touches
    physical stock or StockReservation, purely a what-if forecast like
    everything else in this module."""
    pool = {}
    first_shortage_id = None
    checks = {}

    for order in orders_by_start:
        req = _order_requirement(order)
        if req is None:
            checks[order.id] = None
            continue

        raw_item, raw_kg = req["raw_item"], req["raw_kg"]
        colorant_item, colorant_kg = req["colorant_item"], req["colorant_kg"]
        for item in (raw_item, colorant_item):
            if item is not None and item.id not in pool:
                pool[item.id] = item.quantity

        raw_available = pool[raw_item.id]
        raw_ok = raw_available >= raw_kg
        colorant_available = pool[colorant_item.id] if colorant_item else None
        colorant_ok = colorant_available >= colorant_kg if colorant_item else True
        sufficient = raw_ok and colorant_ok

        if sufficient:
            pool[raw_item.id] -= raw_kg
            status = "OK"
            if pool[raw_item.id] <= raw_item.min_threshold:
                status = "WARNING"
            if colorant_item:
                pool[colorant_item.id] -= colorant_kg
                if pool[colorant_item.id] <= colorant_item.min_threshold:
                    status = "WARNING"
        else:
            status = "INSUFFICIENT"
            if first_shortage_id is None:
                first_shortage_id = order.id

        checks[order.id] = {
            "bottle": req["bottle"].id,
            "bottle_category": req["bottle"].category,
            "raw_material_reference": raw_item.reference,
            "raw_material_required_kg": str(raw_kg),
            "raw_material_physical_kg": str(raw_item.quantity),
            "raw_material_reserved_kg": str(raw_item.quantity - raw_available),
            "raw_material_available_kg": str(raw_available),
            "colorant_reference": colorant_item.reference if colorant_item else "",
            "colorant_required_kg": str(colorant_kg) if colorant_kg is not None else None,
            "colorant_physical_kg": str(colorant_item.quantity) if colorant_item else None,
            "colorant_reserved_kg": str(colorant_item.quantity - colorant_available) if colorant_item else None,
            "colorant_available_kg": str(colorant_available) if colorant_available is not None else None,
            "stock_sufficient": sufficient,
            "stock_status": status,
            "is_first_shortage": False,
        }

    if first_shortage_id is not None:
        checks[first_shortage_id]["is_first_shortage"] = True
    return checks


def calculate_schedule(machine=None):
    """Sequence + timing for the order queue (plan.md §7): grouped by
    machine, ordered automatically — requested_start first (Postgres puts
    NULLs last on ascending order), then id as a FIFO tie-break/fallback for
    orders with no specific date. No manual priority number: to bump an
    order forward, give it an earlier requested_start (or none, to queue it
    by creation order). Each job's start is the previous job's finish on
    that machine; mold-change time is only added when the mold actually
    differs from the previous job's, not on every job.
    `production_time = quantity × time_per_bottle`, normalized to minutes."""
    qs = PlanningOrder.objects.filter(status=PlanningOrderStatus.QUEUED).select_related(
        "machine", "mold", "bottle", "bottle__raw_material", "bottle__colorant",
    )
    if machine is not None:
        qs = qs.filter(machine=machine)

    by_machine = defaultdict(list)
    for order in qs.order_by("machine_id", "requested_start", "id"):
        by_machine[order.machine_id].append(order)

    results = []
    timed_orders = []  # (estimated_start, order) — feeds the global stock pass below
    for orders in by_machine.values():
        cursor = None
        prev_mold_id = None
        for order in orders:
            start = order.requested_start or cursor or timezone.now()
            if cursor and start < cursor:
                # The machine isn't free yet — can't start earlier than the
                # previous job's finish, regardless of a requested_start.
                start = cursor

            mold_change = order.mold_change_min if (prev_mold_id is not None and order.mold_id != prev_mold_id) else 0
            production_min = (order.quantity * float(order.time_per_bottle_sec)) / 60
            finish = start + timedelta(minutes=mold_change) + timedelta(minutes=production_min)

            results.append({
                "id": order.id,
                "machine": order.machine_id,
                "machine_code": order.machine.code,
                "mold": order.mold_id,
                "mold_name": order.mold.name if order.mold else "",
                "product_reference": order.product_reference,
                "color": order.color,
                "quantity": order.quantity,
                "mold_change_min": mold_change,
                "production_time_min": round(production_min, 1),
                "estimated_start": start.isoformat(),
                "estimated_finish": finish.isoformat(),
                "total_duration_min": round(mold_change + production_min, 1),
                "material_check": None,  # filled in below by the global stock pass
            })
            timed_orders.append((start, order))
            cursor = finish
            prev_mold_id = order.mold_id

    # Stock is a shared pool across every machine, so the sequential
    # simulation runs once over ALL machines' orders together, ordered by
    # when each is actually scheduled to start — not per-machine like the
    # timing loop above (an order on machine B starting before one on
    # machine A gets first claim on any material they both need).
    timed_orders.sort(key=lambda pair: pair[0])
    checks = simulate_stock_sequence([order for _, order in timed_orders])
    for row in results:
        row["material_check"] = checks.get(row["id"])
    return results
