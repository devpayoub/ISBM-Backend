from django.db import migrations

RAW_TYPES = {
    "BOTTLE_RAW": "raw_material_qty_g",
    "CAP_RAW": "bouchant_raw_material_qty_g",
}
COLORANT_TYPES = {
    "BOTTLE_COLORANT": "colorant_qty_g",
    "CAP_COLORANT": "bouchant_colorant_qty_g",
}


def backfill(apps, schema_editor):
    BottleCharacteristic = apps.get_model("catalog", "BottleCharacteristic")
    RecipeComponent = apps.get_model("catalog", "RecipeComponent")

    for bottle in BottleCharacteristic.objects.all():
        for component_type, field in RAW_TYPES.items():
            RecipeComponent.objects.update_or_create(
                recipe=bottle, component_type=component_type,
                defaults={"stock_item_id": bottle.raw_material_id, "qty_per_unit_g": getattr(bottle, field)},
            )
        if bottle.colorant_id:
            for component_type, field in COLORANT_TYPES.items():
                RecipeComponent.objects.update_or_create(
                    recipe=bottle, component_type=component_type,
                    defaults={"stock_item_id": bottle.colorant_id, "qty_per_unit_g": getattr(bottle, field)},
                )


def unbackfill(apps, schema_editor):
    RecipeComponent = apps.get_model("catalog", "RecipeComponent")
    RecipeComponent.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_recipecomponent"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
