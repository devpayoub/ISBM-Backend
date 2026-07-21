from django.contrib import admin

from .models import Intervention


@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display = ("id", "alert", "technician", "started_at", "finished_at", "duration_min")
    list_filter = ("technician",)
    readonly_fields = ("duration_min",)
    search_fields = ("action_taken", "parts_used", "notes")
