from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "first_name", "last_name", "role", "shift", "is_on_duty", "is_staff")
    list_filter = ("role", "shift", "is_on_duty", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name", "phone")
    ordering = ("last_name", "first_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personnel", {"fields": ("first_name", "last_name", "phone", "shift", "role")}),
        ("Atelier", {"fields": ("machine_assignment", "is_on_duty")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "role", "shift", "password1", "password2"),
        }),
    )
    readonly_fields = ("last_login", "date_joined")
