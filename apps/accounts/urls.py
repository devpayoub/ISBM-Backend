from django.urls import include, path
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, LogoutView, MeView, ShiftAssignmentViewSet, UserViewSet
from rest_framework.routers import DefaultRouter

TokenRefreshView = extend_schema(tags=["Auth"])(TokenRefreshView)

router = DefaultRouter(trailing_slash=False)
router.register("users", UserViewSet, basename="users")
router.register("shift-assignments", ShiftAssignmentViewSet, basename="shift-assignments")

urlpatterns = [
    path("login", LoginView.as_view(), name="login"),
    path("refresh", TokenRefreshView.as_view(), name="refresh"),
    path("logout", LogoutView.as_view(), name="logout"),
    path("me", MeView.as_view(), name="me"),
    path("", include(router.urls)),
]
