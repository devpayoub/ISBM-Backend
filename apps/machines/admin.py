from django.contrib import admin

from .models import AuxiliaryEquipment, Machine, MachineComponent, Mold, Parameter


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


@admin.register(MachineComponent)
class MachineComponentAdmin(admin.ModelAdmin):
    list_display = ("name", "reference", "machine", "is_active")
    list_filter = ("machine", "is_active")
    search_fields = ("name", "reference")
    autocomplete_fields = ("machine",)


@admin.register(AuxiliaryEquipment)
class AuxiliaryEquipmentAdmin(admin.ModelAdmin):
    list_display = ("name", "reference", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "reference")
    filter_horizontal = ("machines",)


@admin.register(Mold)
class MoldAdmin(admin.ModelAdmin):
    list_display = ("name", "reference", "machine", "is_active")
    list_filter = ("machine", "is_active")
    search_fields = ("name", "reference")
    autocomplete_fields = ("machine",)
