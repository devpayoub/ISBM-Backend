from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AlertCategoryViewSet, AlertViewSet

router = DefaultRouter()
router.register("categories", AlertCategoryViewSet, basename="alert-categories")

urlpatterns = [
    path("", include(router.urls)),
    path("", AlertViewSet.as_view({
        "get": "list", "post": "create"}),
    ),
    path("active/", AlertViewSet.as_view({"get": "active"}), name="alert-active"),
    path("pareto/", AlertViewSet.as_view({"get": "pareto"}), name="alert-pareto"),
    path("stats/", AlertViewSet.as_view({"get": "stats"}), name="alert-stats"),
    path("<int:pk>/", AlertViewSet.as_view({
        "get": "retrieve", "put": "update", "patch": "partial_update",
        "delete": "destroy"}),
    ),
    path("<int:pk>/acknowledge/", AlertViewSet.as_view({"patch": "acknowledge"}), name="alert-acknowledge"),
    path("<int:pk>/resolve/", AlertViewSet.as_view({"patch": "resolve"}), name="alert-resolve"),
    path("<int:pk>/close/", AlertViewSet.as_view({"patch": "close"}), name="alert-close"),
    path("<int:pk>/escalate/", AlertViewSet.as_view({"patch": "escalate"}), name="alert-escalate"),
    path("<int:pk>/comments/", AlertViewSet.as_view({"post": "comments"}), name="alert-comments"),
]
