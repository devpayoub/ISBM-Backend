from django.contrib import admin

from .models import BottleCharacteristic


@admin.register(BottleCharacteristic)
class BottleCharacteristicAdmin(admin.ModelAdmin):
    list_display = ("category", "reference", "raw_material", "colorant", "bouchant_type", "is_active")
    list_filter = ("bouchant_type", "is_active")
    search_fields = ("category", "reference")
