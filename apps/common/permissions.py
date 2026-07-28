from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and getattr(request.user, "role", None) == "ADMIN")


class IsManager(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and getattr(request.user, "role", None) == "MANAGER")


class IsMaintenance(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and getattr(request.user, "role", None) == "MAINTENANCE")


class IsController(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and getattr(request.user, "role", None) == "CONTROLLER")


class IsAdminOrManager(BasePermission):
    def has_permission(self, request, view):
        role = getattr(request.user, "role", None) if request.user else None
        return role in ("ADMIN", "MANAGER")


class IsAdminOrManagerOrMaintenance(BasePermission):
    def has_permission(self, request, view):
        role = getattr(request.user, "role", None) if request.user else None
        return role in ("ADMIN", "MANAGER", "MAINTENANCE")


class IsAdminOrManagerOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        role = getattr(request.user, "role", None) if request.user else None
        return role in ("ADMIN", "MANAGER")


class ReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
