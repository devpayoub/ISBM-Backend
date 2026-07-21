from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CostParameterViewSet, CostRecordViewSet

router = DefaultRouter()
router.register("parameters", CostParameterViewSet, basename="cost-parameters")
router.register("", CostRecordViewSet, basename="cost-records")

urlpatterns = [
    path("", include(router.urls)),
    path("daily/", CostRecordViewSet.as_view({"get": "daily"}), name="cost-daily"),
    path("monthly-report/", CostRecordViewSet.as_view({"get": "monthly_report"}), name="cost-monthly"),
    path("recalc/", CostRecordViewSet.as_view({"post": "recalc"}), name="cost-recalc"),
]
