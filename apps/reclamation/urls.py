from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ReclamationViewSet

router = DefaultRouter(trailing_slash=False)
router.register("reclamations", ReclamationViewSet, basename="reclamations")

urlpatterns = [
    path("", include(router.urls)),
    path("reclamations/resolve-personnel", ReclamationViewSet.as_view({"get": "resolve_personnel_preview"}), name="reclamation-resolve-personnel"),
    path("reclamations/<int:pk>/close", ReclamationViewSet.as_view({"patch": "close"}), name="reclamation-close"),
    path("reclamations/<int:pk>/attachments", ReclamationViewSet.as_view({"post": "add_attachment"}), name="reclamation-add-attachment"),
]
