from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import StockItemViewSet

router = DefaultRouter(trailing_slash=False)
router.register("items", StockItemViewSet, basename="stock-items")

urlpatterns = [
    path("", include(router.urls)),
    path("items/<int:pk>/move", StockItemViewSet.as_view({"post": "move"}), name="stock-item-move"),
    path("items/low-stock", StockItemViewSet.as_view({"get": "low_stock"}), name="stock-low-stock"),
]
