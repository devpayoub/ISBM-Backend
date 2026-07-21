from rest_framework.routers import DefaultRouter

from .views import MachineViewSet, ParameterViewSet

router = DefaultRouter()
router.register("parameters", ParameterViewSet, basename="parameters")

urlpatterns = []

# Register machine routes separately because we still want custom actions wired.
from django.urls import path, include
urlpatterns += [
    path("", include(router.urls)),
    path("", MachineViewSet.as_view({
        "get": "list",
        "post": "create",
    })),
    path("<int:pk>/", MachineViewSet.as_view({
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    })),
    path("<int:pk>/status/", MachineViewSet.as_view({"patch": "status"}), name="machine-status"),
    path("<int:pk>/parameters/", MachineViewSet.as_view({"get": "parameters"}), name="machine-parameters"),
]
