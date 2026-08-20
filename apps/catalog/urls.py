from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BottleCharacteristicViewSet

router = DefaultRouter(trailing_slash=False)
router.register("bottle-characteristics", BottleCharacteristicViewSet, basename="bottle-characteristics")

urlpatterns = [
    path("", include(router.urls)),
]
