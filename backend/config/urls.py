from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import TemplateView

from integrations.api.views import PublicConfigView
from operations.health import HealthView

urlpatterns = [
    path("api/v1/public-config/", PublicConfigView.as_view()),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/integrations/", include("integrations.api.urls")),
    path("api/v1/", include("crm.api.urls")),
    path("admin/", admin.site.urls),
    path("health/", HealthView.as_view(), name="health"),
    path("api/v1/health/", HealthView.as_view(), name="api-health"),
    re_path(
        r"^(?!api(?:/|$)|admin(?:/|$)|health(?:/|$)|static(?:/|$)).*$",
        TemplateView.as_view(template_name="index.html"),
        name="frontend",
    ),
]
