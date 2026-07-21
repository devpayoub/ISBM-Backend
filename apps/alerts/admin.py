from django.contrib import admin

from .models import Alert, AlertCategory, AlertComment


@admin.register(AlertCategory)
class AlertCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "severity_default", "color", "requires_maintenance", "is_active")
    list_filter = ("severity_default", "is_active")


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "machine", "severity", "status", "created_at", "priority_score")
    list_filter = ("severity", "status", "machine", "escalation_level")
    search_fields = ("title", "description", "worker_name")
    ordering = ("-priority_score", "-created_at")
    readonly_fields = (
        "priority_score", "created_at", "updated_at",
        "acknowledged_at", "resolved_at", "closed_at",
    )


@admin.register(AlertComment)
class AlertCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "alert", "user", "created_at")
    search_fields = ("text",)
    ordering = ("-created_at",)
