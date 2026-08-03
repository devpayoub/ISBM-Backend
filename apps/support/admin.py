from django.contrib import admin

from .models import (
    SupplierSolution, Ticket, TicketAttachment, TicketClosure, TicketComment,
    TicketStatusLog,
)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("ticket_number", "machine", "criticality", "status", "created_at")
    list_filter = ("status", "criticality", "machine")
    search_fields = ("ticket_number", "description", "error_code")
    ordering = ("-created_at",)
    readonly_fields = ("ticket_number", "created_at", "updated_at")


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "category", "uploaded_by", "uploaded_at")
    list_filter = ("category",)


@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "user", "created_at")


@admin.register(TicketStatusLog)
class TicketStatusLogAdmin(admin.ModelAdmin):
    list_display = ("ticket", "from_status", "to_status", "decision", "changed_by", "created_at")
    list_filter = ("to_status", "decision")


@admin.register(SupplierSolution)
class SupplierSolutionAdmin(admin.ModelAdmin):
    list_display = ("ticket", "urgency", "proposed_by", "proposed_at")


@admin.register(TicketClosure)
class TicketClosureAdmin(admin.ModelAdmin):
    list_display = ("ticket", "repair_conforms", "total_downtime_min", "closed_by", "closed_at")
