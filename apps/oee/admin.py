from django.contrib import admin

from .models import OEERecord


@admin.register(OEERecord)
class OEERecordAdmin(admin.ModelAdmin):
    list_display = ("date", "machine", "shift", "actual_production", "downtime", "trs_pct")
    list_filter = ("date", "machine", "shift")
    search_fields = ("machine__code",)
    ordering = ("-date", "machine__code")
    readonly_fields = ("availability_pct", "performance_pct", "quality_pct", "trs_pct", "computed_at")

    @admin.display(description="Downtime")
    def downtime(self, obj):
        return f"{obj.total_downtime_min} min"
