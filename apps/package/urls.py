from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PackageViewSet

router = DefaultRouter(trailing_slash=False)
router.register("packages", PackageViewSet, basename="packages")

urlpatterns = [
    path("", include(router.urls)),
    path("packages/resolve-personnel", PackageViewSet.as_view({"get": "resolve_personnel_preview"}), name="package-resolve-personnel"),
]
