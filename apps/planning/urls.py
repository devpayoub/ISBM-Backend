from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PlanningOrderViewSet, ProductionPlanViewSet

router = DefaultRouter(trailing_slash=False)
# "orders" must be registered before the root "" ProductionPlanViewSet
# registration — otherwise its `^(?P<pk>[^/.]+)$` detail pattern shadows
# `/orders` (same issue documented in apps/machines/urls.py).
router.register("orders", PlanningOrderViewSet, basename="planning-orders")
router.register("", ProductionPlanViewSet, basename="planning")

urlpatterns = [
    path("", include(router.urls)),
    path("today", ProductionPlanViewSet.as_view({"get": "today"}), name="planning-today"),
    path("variance-report", ProductionPlanViewSet.as_view({"get": "variance_report"}), name="planning-variance"),
    path("orders/schedule", PlanningOrderViewSet.as_view({"get": "schedule"}), name="planning-orders-schedule"),
]
