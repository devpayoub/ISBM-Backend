from django.contrib import admin

from .models import BottleCharacteristic, RecipeComponent


@admin.register(BottleCharacteristic)
class BottleCharacteristicAdmin(admin.ModelAdmin):
    list_display = ("category", "reference", "raw_material", "colorant", "bouchant_type", "is_active")
    list_filter = ("bouchant_type", "is_active")
    search_fields = ("category", "reference")


@admin.register(RecipeComponent)
class RecipeComponentAdmin(admin.ModelAdmin):
    list_display = ("recipe", "component_type", "stock_item", "qty_per_unit_g")
    list_filter = ("component_type",)
    search_fields = ("recipe__category", "stock_item__reference")
