from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import InterventionViewSet, PreventiveMaintenanceViewSet

router = DefaultRouter(trailing_slash=False)
router.register("interventions", InterventionViewSet, basename="interventions")
router.register("preventive", PreventiveMaintenanceViewSet, basename="preventive")

urlpatterns = [
    path("", include(router.urls)),
    path("interventions/<int:pk>/finish", InterventionViewSet.as_view({"patch": "finish"}), name="intervention-finish"),
    path("my-tasks", InterventionViewSet.as_view({"get": "my_tasks"}), name="maintenance-my-tasks"),
    path("queue", InterventionViewSet.as_view({"get": "queue"}), name="maintenance-queue"),
    path("by-day", InterventionViewSet.as_view({"get": "by_day"}), name="maintenance-by-day"),
    path("mttr", InterventionViewSet.as_view({"get": "mttr"}), name="maintenance-mttr"),
]
