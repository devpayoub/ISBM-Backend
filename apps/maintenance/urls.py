from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import InterventionViewSet

router = DefaultRouter()
router.register("interventions", InterventionViewSet, basename="interventions")

urlpatterns = [
    path("", include(router.urls)),
    path("interventions/<int:pk>/finish/", InterventionViewSet.as_view({"patch": "finish"}), name="intervention-finish"),
    path("my-tasks/", InterventionViewSet.as_view({"get": "my_tasks"}), name="maintenance-my-tasks"),
    path("mttr/", InterventionViewSet.as_view({"get": "mttr"}), name="maintenance-mttr"),
]
