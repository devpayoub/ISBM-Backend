from django.contrib import admin

from .models import (
    ChecklistItem, ChecklistSection, ChecklistTemplate, Intervention,
    MaintenanceControl, MaintenanceControlResult, PreventiveMaintenance,
)


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


class ChecklistSectionInline(admin.TabularInline):
    model = ChecklistSection
    extra = 0


@admin.register(ChecklistTemplate)
class ChecklistTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "name", "is_active")
    inlines = [ChecklistSectionInline]


class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 0


@admin.register(ChecklistSection)
class ChecklistSectionAdmin(admin.ModelAdmin):
    list_display = ("id", "template", "name", "order")
    list_filter = ("template",)
    inlines = [ChecklistItemInline]


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display = ("id", "section", "text", "order")
    list_filter = ("section__template",)
    search_fields = ("text",)


class MaintenanceControlResultInline(admin.TabularInline):
    model = MaintenanceControlResult
    extra = 0
    readonly_fields = ("item",)


@admin.register(MaintenanceControl)
class MaintenanceControlAdmin(admin.ModelAdmin):
    list_display = ("id", "target_label", "date", "shift", "template", "controller", "confirmed_at")
    list_filter = ("shift", "template", "confirmed_at")
    search_fields = ("machine__code", "equipment__name")
    inlines = [MaintenanceControlResultInline]
