from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CostParameterViewSet, CostRecordViewSet

router = DefaultRouter(trailing_slash=False)
router.register("", CostRecordViewSet, basename="cost-records")

urlpatterns = [
    # IMPORTANT: manual parameters routes come before the router include so
    # ``PUT /parameters`` (bulk update) can be wired alongside list/create,
    # which DRF's router does not support on the collection route.
    path("parameters", CostParameterViewSet.as_view({
        "get": "list", "post": "create", "put": "bulk_update",
    })),
    path("parameters/active", CostParameterViewSet.as_view({"get": "active"}), name="cost-parameters-active"),
    path("parameters/<int:pk>", CostParameterViewSet.as_view({
        "get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy",
    })),
    path("", include(router.urls)),
    path("daily", CostRecordViewSet.as_view({"get": "daily"}), name="cost-daily"),
    path("monthly-report", CostRecordViewSet.as_view({"get": "monthly_report"}), name="cost-monthly"),
    path("recalc", CostRecordViewSet.as_view({"post": "recalc"}), name="cost-recalc"),
]
