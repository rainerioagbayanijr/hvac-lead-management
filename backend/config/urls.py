from django.contrib import admin
from django.urls import include, path

from operations.health import HealthView

urlpatterns = [
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/", include("crm.api.urls")),
    path("admin/", admin.site.urls),
    path("health/", HealthView.as_view(), name="health"),
    path("api/v1/health/", HealthView.as_view(), name="api-health"),
]
