from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PlanningOrderViewSet

router = DefaultRouter(trailing_slash=False)
router.register("orders", PlanningOrderViewSet, basename="planning-orders")

urlpatterns = [
    path("", include(router.urls)),
    path("orders/schedule", PlanningOrderViewSet.as_view({"get": "schedule"}), name="planning-orders-schedule"),
]
