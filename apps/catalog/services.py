from decimal import Decimal


def max_producible(bottle) -> int:
    """How many more bottles this recipe could produce from current Stock
    (the inverse of apps.planning.services._material_check, which asks
    "is stock enough for N bottles" — this asks "what's the max N").
    Body + bouchant quantities share the same StockItem references on
    BottleCharacteristic, so they're summed before dividing, same as
    Package's auto-consumption and Planning's material check."""
    raw_per_bottle_kg = (bottle.raw_material_qty_g + bottle.bouchant_raw_material_qty_g) / Decimal("1000")
    raw_capacity = int(bottle.raw_material.quantity // raw_per_bottle_kg) if raw_per_bottle_kg > 0 else None

    colorant_qty_g = bottle.colorant_qty_g + bottle.bouchant_colorant_qty_g
    colorant_capacity = None
    if bottle.colorant and colorant_qty_g:
        colorant_per_bottle_kg = colorant_qty_g / Decimal("1000")
        colorant_capacity = int(bottle.colorant.quantity // colorant_per_bottle_kg)

    capacities = [c for c in (raw_capacity, colorant_capacity) if c is not None]
    return min(capacities) if capacities else 0
