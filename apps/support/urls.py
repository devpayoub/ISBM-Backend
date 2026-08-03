from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SupportKPIsView, TicketViewSet

router = DefaultRouter()
router.register("tickets", TicketViewSet, basename="tickets")

urlpatterns = [
    path("kpis", SupportKPIsView.as_view(), name="support-kpis"),
    path("", include(router.urls)),
]
