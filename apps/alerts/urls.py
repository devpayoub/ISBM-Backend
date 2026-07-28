from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AlertCategoryViewSet, AlertViewSet

router = DefaultRouter(trailing_slash=False)
router.register("categories", AlertCategoryViewSet, basename="alert-categories")

# IMPORTANT: list the manual ``AlertViewSet`` URLs *before* including the
# router URLs. Otherwise the router's API-root view (``""``) shadows the
# alert list endpoint and ``GET /api/v1/alerts`` returns the root doc
# (``{"categories": "..."}``) instead of the actual alerts list.
urlpatterns = [
    path("", AlertViewSet.as_view({
        "get": "list", "post": "create"}),
    ),
    path("active", AlertViewSet.as_view({"get": "active"}), name="alert-active"),
    path("pareto", AlertViewSet.as_view({"get": "pareto"}), name="alert-pareto"),
    path("stats", AlertViewSet.as_view({"get": "stats"}), name="alert-stats"),
    path("<int:pk>", AlertViewSet.as_view({
        "get": "retrieve", "put": "update", "patch": "partial_update",
        "delete": "destroy"}),
    ),
    path("<int:pk>/acknowledge", AlertViewSet.as_view({"patch": "acknowledge"}), name="alert-acknowledge"),
    path("<int:pk>/start", AlertViewSet.as_view({"patch": "start"}), name="alert-start"),
    path("<int:pk>/resolve", AlertViewSet.as_view({"patch": "resolve"}), name="alert-resolve"),
    path("<int:pk>/close", AlertViewSet.as_view({"patch": "close"}), name="alert-close"),
    path("<int:pk>/escalate", AlertViewSet.as_view({"patch": "escalate"}), name="alert-escalate"),
    path("<int:pk>/comments", AlertViewSet.as_view({"post": "comments"}), name="alert-comments"),
    path("", include(router.urls)),
]
