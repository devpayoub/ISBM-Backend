from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import OEEViewSet

router = DefaultRouter(trailing_slash=False)
router.register("", OEEViewSet, basename="oee")

urlpatterns = [
    path("", include(router.urls)),
    path("current", OEEViewSet.as_view({"get": "current"}), name="oee-current"),
    path("recalc", OEEViewSet.as_view({"post": "recalc"}), name="oee-recalc"),
    path("trends", OEEViewSet.as_view({"get": "trends"}), name="oee-trends"),
]
