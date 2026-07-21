from django.contrib import admin

from .models import ProductionPlan


@admin.register(ProductionPlan)
class ProductionPlanAdmin(admin.ModelAdmin):
    list_display = ("date", "machine", "product", "target_bph", "actual_bph", "variance", "variance_pct")
    list_filter = ("date", "machine")
    search_fields = ("product", "notes")
    ordering = ("-date", "machine__code")
