from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from .models import StockItem, StockMovement, StockReservation


def apply_movement(item: StockItem, movement_type: str, delta, reason: str, user) -> StockMovement:
    """Single chokepoint for every stock quantity change — used by
    StockItemViewSet.move() directly, and by apps.package to auto-consume
    raw material/colorant when a bag is created. Never allows the
    resulting quantity to go negative."""
    quantity_before = item.quantity
    quantity_after = quantity_before + delta
    if quantity_after < 0:
        raise ValidationError(
            f"Stock insuffisant pour {item.name} ({item.reference}) : "
            f"{quantity_before} {item.unit} disponible, {abs(delta)} {item.unit} requis."
        )
    with transaction.atomic():
        item.quantity = quantity_after
        item.save(update_fields=["quantity", "updated_at"])
        movement = StockMovement.objects.create(
            stock_item=item, type=movement_type, delta=delta,
            quantity_before=quantity_before, quantity_after=quantity_after,
            reason=reason, created_by=user,
        )
    return movement


@dataclass
class MaterialRequirement:
    stock_item_id: int
    stock_item_reference: str
    stock_item_name: str
    unit: str
    component_type: str
    qty_per_unit_g: Decimal
    required_qty_kg: Decimal
    # Combined requirement across every sibling RecipeComponent that shares
    # this stock_item (body + cap usually draw from the same material) —
    # availability/status below are judged against this, not required_qty_kg
    # alone, so two components quietly summing past physical stock can't
    # each report "sufficient" in isolation.
    stock_item_total_required_kg: Decimal
    physical_stock_kg: Decimal
    reserved_stock_kg: Decimal
    available_stock_kg: Decimal
    projected_remaining_kg: Decimal
    min_threshold_kg: Decimal
    status: str  # "OK" | "WARNING" | "INSUFFICIENT"


def _reserved_totals(stock_item_ids, exclude_order=None) -> dict:
    """Reserved quantity per stock_item, in kg, summed across every
    QUEUED order's reservations (StockReservation rows only exist for
    QUEUED orders — sync_reservations_for_order() clears them otherwise).
    `exclude_order` must be passed when checking that same order's own
    sufficiency — its reservation already exists in the DB by the time this
    runs, so without excluding it here, its own requirement gets subtracted
    from "available" twice (once via its reservation, again via this same
    call's own required_qty)."""
    qs = StockReservation.objects.filter(stock_item_id__in=stock_item_ids)
    if exclude_order is not None:
        qs = qs.exclude(planning_order=exclude_order)
    rows = qs.values("stock_item_id").annotate(total=Sum("quantity"))
    return {row["stock_item_id"]: row["total"] for row in rows}


def sync_reservations_for_order(order) -> None:
    """Recompute one PlanningOrder's reservations from scratch — delete then
    recreate, matching the "always recomputed, never hand-edited" convention
    used everywhere else in this codebase. Call on every PlanningOrder
    create/update (destroy is handled by StockReservation's CASCADE FK).
    Clears reservations entirely for an order with no recipe or that isn't
    QUEUED — only a queued order still competing for physical stock should
    hold one."""
    from apps.planning.models import PlanningOrderStatus

    StockReservation.objects.filter(planning_order=order).delete()
    if not order.bottle or order.status != PlanningOrderStatus.QUEUED:
        return

    for component in order.bottle.components.all():
        qty_kg = (component.qty_per_unit_g * order.quantity) / Decimal("1000")
        StockReservation.objects.create(
            planning_order=order, stock_item=component.stock_item,
            component_type=component.component_type, quantity=qty_kg,
        )


def calculate_material_requirements(bottle, quantity, exclude_order=None) -> list[MaterialRequirement]:
    """Single source of truth for "how much material does N of this bottle
    recipe need, and is there enough Stock." Read by Planning (order
    sufficiency), Catalog (production capacity), and Package (auto-
    consumption) — none of them should re-derive this math independently.
    Returns one row per RecipeComponent (body/cap × raw material/colorant).

    Pass `exclude_order` when checking a specific PlanningOrder's own
    sufficiency (its reservation already exists by the time this runs —
    see _reserved_totals). Leave it None for capacity/what-if checks that
    aren't about an order that has already reserved anything."""
    components = list(bottle.components.select_related("stock_item").all())

    totals_by_item: dict = defaultdict(Decimal)
    for c in components:
        totals_by_item[c.stock_item_id] += (c.qty_per_unit_g * quantity) / Decimal("1000")

    reserved_by_item = _reserved_totals([c.stock_item_id for c in components], exclude_order=exclude_order)

    rows = []
    for c in components:
        item = c.stock_item
        required_kg = (c.qty_per_unit_g * quantity) / Decimal("1000")
        total_required_kg = totals_by_item[item.id]
        reserved_kg = reserved_by_item.get(item.id, Decimal("0"))
        available_kg = item.quantity - reserved_kg
        projected_kg = available_kg - total_required_kg
        if projected_kg < 0:
            status = "INSUFFICIENT"
        elif projected_kg <= item.min_threshold:
            status = "WARNING"
        else:
            status = "OK"
        rows.append(MaterialRequirement(
            stock_item_id=item.id, stock_item_reference=item.reference, stock_item_name=item.name,
            unit=item.unit, component_type=c.component_type, qty_per_unit_g=c.qty_per_unit_g,
            required_qty_kg=required_kg, stock_item_total_required_kg=total_required_kg,
            physical_stock_kg=item.quantity, reserved_stock_kg=reserved_kg,
            available_stock_kg=available_kg, projected_remaining_kg=projected_kg,
            min_threshold_kg=item.min_threshold, status=status,
        ))
    return rows
