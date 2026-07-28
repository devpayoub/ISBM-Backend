from django.contrib import admin

from .models import Intervention, PreventiveMaintenance


@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display = ("id", "alert", "technician", "started_at", "finished_at", "duration_min", "verified")
    list_filter = ("technician", "verified")
    readonly_fields = ("duration_min",)
    search_fields = ("action_taken", "parts_used", "notes")


@admin.register(PreventiveMaintenance)
class PreventiveMaintenanceAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "machine", "frequency", "next_due", "status", "assigned_to")
    list_filter = ("frequency", "status", "machine")
    search_fields = ("task",)
