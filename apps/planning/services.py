from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.catalog.models import RecipeComponentType
from apps.stock.services import calculate_material_requirements

from .models import PlanningOrder, PlanningOrderStatus

_RAW_TYPES = (RecipeComponentType.BOTTLE_RAW, RecipeComponentType.CAP_RAW)
_COLORANT_TYPES = (RecipeComponentType.BOTTLE_COLORANT, RecipeComponentType.CAP_COLORANT)


def _material_check(order):
    """How much raw material/colorant this order needs vs. what's on hand
    right now — only computed when the order has a linked bottle recipe,
    since that's what supplies the per-bottle grams. Delegates to the
    central apps.stock.services.calculate_material_requirements() (single
    source of truth, also used by Catalog capacity and Package
    auto-consumption) instead of re-deriving the grams-per-bottle math."""
    bottle = order.bottle
    if not bottle:
        return None

    rows = calculate_material_requirements(bottle, order.quantity)
    raw_rows = [r for r in rows if r.component_type in _RAW_TYPES]
    colorant_rows = [r for r in rows if r.component_type in _COLORANT_TYPES]

    raw_required_kg = sum((r.required_qty_kg for r in raw_rows), Decimal("0"))
    raw_available_kg = raw_rows[0].available_stock_kg if raw_rows else Decimal("0")
    raw_ok = raw_rows[0].status != "INSUFFICIENT" if raw_rows else True

    colorant_required_kg = None
    colorant_available_kg = None
    colorant_ok = True
    if colorant_rows:
        colorant_required_kg = sum((r.required_qty_kg for r in colorant_rows), Decimal("0"))
        colorant_available_kg = colorant_rows[0].available_stock_kg
        colorant_ok = colorant_rows[0].status != "INSUFFICIENT"

    return {
        "bottle": bottle.id,
        "bottle_category": bottle.category,
        "raw_material_reference": bottle.raw_material.reference,
        "raw_material_required_kg": str(raw_required_kg),
        "raw_material_available_kg": str(raw_available_kg),
        "colorant_reference": bottle.colorant.reference if bottle.colorant else "",
        "colorant_required_kg": str(colorant_required_kg) if colorant_required_kg is not None else None,
        "colorant_available_kg": str(colorant_available_kg) if colorant_available_kg is not None else None,
        "stock_sufficient": raw_ok and colorant_ok,
    }


def calculate_schedule(machine=None):
    """Sequence + timing for the order queue (plan.md §7): grouped by
    machine, ordered by priority then id (stable tie-break — bumping an
    order to the front of its machine's queue is just giving it a lower
    priority number than the rest). Each job's start is the previous job's
    finish on that machine; mold-change time is only added when the mold
    actually differs from the previous job's, not on every job.
    `production_time = quantity × time_per_bottle`, normalized to minutes."""
    qs = PlanningOrder.objects.filter(status=PlanningOrderStatus.QUEUED).select_related(
        "machine", "mold", "bottle", "bottle__raw_material", "bottle__colorant",
    )
    if machine is not None:
        qs = qs.filter(machine=machine)

    by_machine = defaultdict(list)
    for order in qs.order_by("machine_id", "priority", "id"):
        by_machine[order.machine_id].append(order)

    results = []
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
                "priority": order.priority,
                "mold_change_min": mold_change,
                "production_time_min": round(production_min, 1),
                "estimated_start": start.isoformat(),
                "estimated_finish": finish.isoformat(),
                "total_duration_min": round(mold_change + production_min, 1),
                "material_check": _material_check(order),
            })
            cursor = finish
            prev_mold_id = order.mold_id
    return results
