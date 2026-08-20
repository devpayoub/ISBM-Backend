from django.contrib import admin

from .models import Reclamation, ReclamationAttachment


@admin.register(Reclamation)
class ReclamationAdmin(admin.ModelAdmin):
    list_display = ("reference", "client", "reported_at", "severity", "status", "machine")
    list_filter = ("status", "severity")
    search_fields = ("reference", "client", "description")
    readonly_fields = ("reference", "resolved_personnel")


@admin.register(ReclamationAttachment)
class ReclamationAttachmentAdmin(admin.ModelAdmin):
    list_display = ("reclamation", "uploaded_by", "uploaded_at")
