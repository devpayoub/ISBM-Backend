from django.contrib import admin

from .models import Package


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ("reference", "machine", "bottle_count", "supplier", "production_started_at", "production_finished_at")
    list_filter = ("machine", "supplier")
    search_fields = ("reference", "raw_material_reference_snapshot", "color_reference_snapshot", "supplier")
    readonly_fields = ("reference", "raw_material_reference_snapshot", "color_reference_snapshot", "personnel_snapshot")
