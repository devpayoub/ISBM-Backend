from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from .models import StockItem, StockMovement, StockReservation


def apply_movement(
    item: StockItem, movement_type: str, delta, reason: str, user,
    source_type: str = "", source_id: int | None = None,
) -> StockMovement:
    """Single chokepoint for every stock quantity change — used by
    StockItemViewSet.move() directly, and by apps.package to auto-consume
    raw material/colorant when a bag is created. Never allows the
    resulting quantity to go negative. source_type/source_id are optional
    (plain manual receipts/adjustments don't set them) — when given, the
    partial unique constraint on StockMovement guarantees this exact
    source+item+type combination can never be recorded twice; prefer
    apply_movement_idempotent() below over calling this directly with a
    source, since that one turns the resulting IntegrityError into a
    graceful no-op instead of a crash."""
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
            reason=reason, created_by=user, source_type=source_type, source_id=source_id,
        )
    return movement


def apply_movement_idempotent(
    item: StockItem, movement_type: str, delta, reason: str, user,
    source_type: str, source_id: int,
):
    """Consumption path for anything that must never double-charge stock
    for the same production event (Package auto-consumption today,
    Production-entry validation once that exists in a later phase) — the
    same (source_type, source_id, stock_item, type) can only ever produce
    one movement. Checks first for the common case, then falls back to
    catching the unique-constraint violation for the rare race between two
    near-simultaneous requests for the same source. Returns
    (movement, created) — created=False means this exact source was
    already recorded and nothing changed on this call."""
    existing = StockMovement.objects.filter(
        stock_item=item, type=movement_type, source_type=source_type, source_id=source_id,
    ).first()
    if existing:
        return existing, False
    try:
        movement = apply_movement(item, movement_type, delta, reason, user, source_type=source_type, source_id=source_id)
        return movement, True
    except IntegrityError:
        return StockMovement.objects.get(
            stock_item=item, type=movement_type, source_type=source_type, source_id=source_id,
        ), False


def raw_and_colorant_requirement(bottle, quantity):
    """Aggregate a bottle recipe's requirement into the two pools every
    consumer actually cares about — raw material and colorant — combining
    body+cap per stock_item (RecipeComponent's finer BOTTLE_RAW/CAP_RAW/etc.
    split is for display; anything that deducts or checks stock wants the
    combined total). Returns (raw_item, raw_kg, colorant_item, colorant_kg)
    — colorant_item/colorant_kg are None if the recipe has no colorant.
    Shared by Planning's schedule simulation and Package's auto-consumption
    so both draw the same amount for the same recipe+quantity."""
    from apps.catalog.models import RecipeComponentType

    raw_types = (RecipeComponentType.BOTTLE_RAW, RecipeComponentType.CAP_RAW)
    colorant_types = (RecipeComponentType.BOTTLE_COLORANT, RecipeComponentType.CAP_COLORANT)
    components = list(bottle.components.select_related("stock_item").all())
    raw = [c for c in components if c.component_type in raw_types]
    colorant = [c for c in components if c.component_type in colorant_types]

    raw_item = raw[0].stock_item if raw else None
    raw_kg = sum((c.qty_per_unit_g for c in raw), Decimal("0")) * quantity / Decimal("1000")
    colorant_item = colorant[0].stock_item if colorant else None
    colorant_kg = (
        sum((c.qty_per_unit_g for c in colorant), Decimal("0")) * quantity / Decimal("1000")
        if colorant else None
    )
    return raw_item, raw_kg, colorant_item, colorant_kg


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
