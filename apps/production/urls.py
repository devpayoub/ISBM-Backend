from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProductionEntryViewSet

router = DefaultRouter()
router.register("", ProductionEntryViewSet, basename="production-entries")

urlpatterns = [
    path("", include(router.urls)),
    path("bulk/", ProductionEntryViewSet.as_view({"post": "bulk"}), name="production-bulk"),
    path("daily-summary/", ProductionEntryViewSet.as_view({"get": "daily-summary"}), name="production-daily-summary"),
    path("shift-summary/", ProductionEntryViewSet.as_view({"get": "shift-summary"}), name="production-shift-summary"),
]
