from rest_framework.routers import DefaultRouter

from .views import MachineViewSet, ParameterViewSet

router = DefaultRouter(trailing_slash=False)
router.register("parameters", ParameterViewSet, basename="parameters")

# Register machine routes separately because we still want custom actions wired.
from django.urls import path, include

# IMPORTANT: list the manual ``MachineViewSet`` URLs *before* including the
# router URLs. Otherwise the router's API-root view (``""``) shadows the
# machine list endpoint and ``GET /api/v1/machines`` returns the root doc
# (``{"parameters": "..."}``) instead of the actual machine list.
urlpatterns = [
    path("", MachineViewSet.as_view({
        "get": "list",
        "post": "create",
    })),
    path("<int:pk>", MachineViewSet.as_view({
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    })),
    path("<int:pk>/status", MachineViewSet.as_view({"patch": "status"}), name="machine-status"),
    path("<int:pk>/parameters", MachineViewSet.as_view({"get": "parameters"}), name="machine-parameters"),
    path("", include(router.urls)),
]
