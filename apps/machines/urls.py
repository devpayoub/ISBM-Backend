from rest_framework.routers import DefaultRouter

from apps.common.permissions import IsSupplier
from rest_framework.permissions import IsAuthenticated

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
    # `.as_view()` is called directly here (no router), so an `@action`'s
    # `permission_classes` kwarg is never applied automatically — a router
    # is what normally merges it into initkwargs. Pass it explicitly instead.
    path("mine", MachineViewSet.as_view({"get": "mine"}, permission_classes=[IsAuthenticated, IsSupplier]),
         name="machine-mine"),
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
