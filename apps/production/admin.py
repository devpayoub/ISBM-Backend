from django.contrib import admin

from .models import ProductionEntry


@admin.register(ProductionEntry)
class ProductionEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "hour", "machine", "shift", "bottles_produced", "caps_produced", "reject_pct", "downtime_min")
    list_filter = ("date", "machine", "shift")
    search_fields = ("machine__code", "downtime_reason")
    ordering = ("-date", "-hour")
