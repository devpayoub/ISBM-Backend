from django.contrib import admin

from .models import CostParameter, CostRecord


@admin.register(CostParameter)
class CostParameterAdmin(admin.ModelAdmin):
    list_display = ("name", "label", "value", "unit", "is_active", "effective_from")
    list_filter = ("is_active",)


@admin.register(CostRecord)
class CostRecordAdmin(admin.ModelAdmin):
    list_display = ("date", "machine", "shift", "total_cost", "production_count", "cost_per_bottle")
    list_filter = ("date", "machine", "shift")
    search_fields = ("machine__code",)
    ordering = ("-date", "machine__code")
    readonly_fields = ("total_cost", "cost_per_bottle", "computed_at")
