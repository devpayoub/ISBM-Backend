from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AuditDocumentViewSet, NonConformityViewSet

router = DefaultRouter()
router.register("nc", NonConformityViewSet, basename="nc")
router.register("audit", AuditDocumentViewSet, basename="audit")

urlpatterns = [
    path("", include(router.urls)),
]
