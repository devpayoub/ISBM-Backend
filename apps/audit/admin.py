from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "target_type", "target_id")
    list_filter = ("action",)
    search_fields = ("action", "detail", "user__email")
    readonly_fields = ("user", "action", "target_type", "target_id", "detail", "created_at")
