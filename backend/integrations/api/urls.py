from django.urls import path

from integrations.api.views import (
    EmailExecutionListView,
    IntegrationStatusView,
    RetryExecutionView,
)
from integrations.api.webhooks import ResendWebhookView

urlpatterns = [
    path("status/", IntegrationStatusView.as_view()),
    path("executions/", EmailExecutionListView.as_view()),
    path("executions/<uuid:pk>/retry/", RetryExecutionView.as_view()),
    path("resend/webhook/", ResendWebhookView.as_view()),
]
