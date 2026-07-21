from django.contrib import admin

from .models import Machine, Parameter


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "type", "status", "nominal_bph", "is_active")
    list_filter = ("type", "status", "is_active")
    search_fields = ("code", "name", "location")
    ordering = ("code",)


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "value", "unit", "category", "is_active", "effective_from")
    list_filter = ("category", "is_active")
    search_fields = ("key", "label")
    ordering = ("category", "key")
