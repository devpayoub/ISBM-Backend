from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, ShiftAssignment


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
        ("Fournisseur (SAV)", {
            "fields": ("assigned_machines",),
            "description": "Machines que ce fournisseur peut voir/traiter dans le module Support/SAV. "
                            "Ne s'applique que si le rôle est \"Fournisseur\".",
        }),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "role", "shift", "password1", "password2"),
        }),
    )
    readonly_fields = ("last_login", "date_joined")
    filter_horizontal = ("assigned_machines", "groups", "user_permissions")


@admin.register(ShiftAssignment)
class ShiftAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "machine", "shift", "starts_at", "ends_at")
    list_filter = ("shift", "machine")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    autocomplete_fields = ("user", "machine")
    ordering = ("-starts_at",)
