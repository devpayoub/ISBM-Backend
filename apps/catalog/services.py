from dataclasses import dataclass

from .models import RecipeComponent, RecipeComponentType


def sync_recipe_components(bottle) -> None:
    """Keep RecipeComponent (the normalized read-side) in step with
    BottleCharacteristic's denormalized edit-side fields. Called after every
    create/update in BottleCharacteristicViewSet so the Settings UI doesn't
    need to change — it still edits raw_material_qty_g etc. directly, this
    just re-derives the component rows every save. Body and cap share the
    same raw_material/colorant StockItem (only quantities differ), matching
    the model's existing behavior everywhere else (Package auto-consumption,
    Planning material checks)."""
    RecipeComponent.objects.update_or_create(
        recipe=bottle, component_type=RecipeComponentType.BOTTLE_RAW,
        defaults={"stock_item": bottle.raw_material, "qty_per_unit_g": bottle.raw_material_qty_g},
    )
    RecipeComponent.objects.update_or_create(
        recipe=bottle, component_type=RecipeComponentType.CAP_RAW,
        defaults={"stock_item": bottle.raw_material, "qty_per_unit_g": bottle.bouchant_raw_material_qty_g},
    )
    if bottle.colorant:
        RecipeComponent.objects.update_or_create(
            recipe=bottle, component_type=RecipeComponentType.BOTTLE_COLORANT,
            defaults={"stock_item": bottle.colorant, "qty_per_unit_g": bottle.colorant_qty_g},
        )
        RecipeComponent.objects.update_or_create(
            recipe=bottle, component_type=RecipeComponentType.CAP_COLORANT,
            defaults={"stock_item": bottle.colorant, "qty_per_unit_g": bottle.bouchant_colorant_qty_g},
        )
    else:
        RecipeComponent.objects.filter(
            recipe=bottle,
            component_type__in=[RecipeComponentType.BOTTLE_COLORANT, RecipeComponentType.CAP_COLORANT],
        ).delete()


@dataclass
class CapacityResult:
    # Ignores reservations — "if every other queued order vanished right
    # now, how many could we make." Always >= available_capacity.
    physical_capacity: int
    # Reservation-aware — "how many can we ACTUALLY still make," accounting
    # for what every other queued/in-progress order has already claimed.
    # This is the number Package/Planning care about; physical_capacity is
    # shown alongside it purely as context ("stock exists, but it's spoken
    # for").
    available_capacity: int
    # Reference/name of whichever stock_item caps available_capacity — the
    # one thing you'd need to restock to raise this recipe's capacity.
    # Empty string if the recipe has no components (nothing to limit on).
    limiting_component: str
    limiting_component_name: str


def max_producible(bottle) -> CapacityResult:
    """How many more bottles this recipe could produce from current Stock,
    and which single material is the bottleneck. Delegates to the central
    apps.stock.services.calculate_material_requirements() (per-unit
    quantity=1) instead of re-deriving the grams-per-bottle math — every
    RecipeComponent sharing a stock_item is already aggregated there, so
    this just floors each stock_item's physical/available quantity by its
    per-unit requirement and takes the min of each."""
    from apps.stock.services import calculate_material_requirements

    rows = calculate_material_requirements(bottle, 1)
    seen_items = set()
    physical_capacity = None
    available_capacity = None
    limiting_component = ""
    limiting_component_name = ""
    for row in rows:
        if row.stock_item_id in seen_items:
            continue
        seen_items.add(row.stock_item_id)
        if row.stock_item_total_required_kg <= 0:
            continue
        phys = int(row.physical_stock_kg // row.stock_item_total_required_kg)
        avail = int(row.available_stock_kg // row.stock_item_total_required_kg)
        physical_capacity = phys if physical_capacity is None else min(physical_capacity, phys)
        if available_capacity is None or avail < available_capacity:
            available_capacity = avail
            limiting_component = row.stock_item_reference
            limiting_component_name = row.stock_item_name
        else:
            available_capacity = min(available_capacity, avail)

    return CapacityResult(
        physical_capacity=physical_capacity or 0,
        available_capacity=available_capacity or 0,
        limiting_component=limiting_component,
        limiting_component_name=limiting_component_name,
    )
