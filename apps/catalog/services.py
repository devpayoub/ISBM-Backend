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


def max_producible(bottle) -> int:
    """How many more bottles this recipe could produce from current Stock.
    Delegates to the central apps.stock.services.calculate_material_
    requirements() (per-unit quantity=1) instead of re-deriving the
    grams-per-bottle math — every RecipeComponent sharing a stock_item is
    already aggregated there, so this just floors each stock_item's
    available quantity by its per-unit requirement and takes the min."""
    from apps.stock.services import calculate_material_requirements

    rows = calculate_material_requirements(bottle, 1)
    capacities = []
    seen_items = set()
    for row in rows:
        if row.stock_item_id in seen_items:
            continue
        seen_items.add(row.stock_item_id)
        if row.stock_item_total_required_kg > 0:
            capacities.append(int(row.available_stock_kg // row.stock_item_total_required_kg))
    return min(capacities) if capacities else 0
