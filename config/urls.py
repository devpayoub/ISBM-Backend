from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", TemplateView.as_view(template_name="floor_screen.html"), name="floor-screen"),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/machines/", include("apps.machines.urls")),
    path("api/v1/alerts/", include("apps.alerts.urls")),
    path("api/v1/maintenance/", include("apps.maintenance.urls")),
    path("api/v1/production/", include("apps.production.urls")),
    path("api/v1/oee/", include("apps.oee.urls")),
    path("api/v1/costs/", include("apps.costs.urls")),
    path("api/v1/planning/", include("apps.planning.urls")),
    path("api/v1/dashboard/", include("apps.dashboard.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
