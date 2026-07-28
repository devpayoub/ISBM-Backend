from django.contrib import admin

from .models import AuditDocument, NonConformity


@admin.register(NonConformity)
class NonConformityAdmin(admin.ModelAdmin):
    list_display = ("nc_number", "type", "source", "status", "machine", "opened_by", "opened_at")
    list_filter = ("type", "source", "status")
    search_fields = ("nc_number", "description", "product")
    readonly_fields = ("nc_number", "opened_at")


@admin.register(AuditDocument)
class AuditDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "clause", "version", "status", "uploaded_by", "uploaded_at")
    list_filter = ("status", "clause")
    search_fields = ("title", "clause")
