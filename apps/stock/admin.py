from django.contrib import admin

from .models import StockItem, StockMovement


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ("name", "reference", "type", "quantity", "unit", "min_threshold", "is_active")
    list_filter = ("type", "is_active")
    search_fields = ("name", "reference", "supplier", "batch")
    readonly_fields = ("quantity",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("stock_item", "type", "delta", "quantity_before", "quantity_after", "created_by", "created_at")
    list_filter = ("type",)
    search_fields = ("stock_item__name", "stock_item__reference", "reason")
