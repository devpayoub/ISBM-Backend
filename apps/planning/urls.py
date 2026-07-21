from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProductionPlanViewSet

router = DefaultRouter()
router.register("", ProductionPlanViewSet, basename="planning")

urlpatterns = [
    path("", include(router.urls)),
    path("today/", ProductionPlanViewSet.as_view({"get": "today"}), name="planning-today"),
    path("variance-report/", ProductionPlanViewSet.as_view({"get": "variance_report"}), name="planning-variance"),
]
