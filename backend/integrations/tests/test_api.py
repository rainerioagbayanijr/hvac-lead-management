from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from crm.models import Lead
from integrations.jobs import process_due
from integrations.models import EmailExecution

User = get_user_model()


class IntegrationApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("integration_admin", role=User.Role.ADMIN)
        self.staff = User.objects.create_user("integration_staff")
        self.lead = Lead.objects.create(
            name="Synthetic HVAC customer", email="customer@example.test", service_type="repair"
        )
        self.execution = EmailExecution.objects.create(
            lead=self.lead,
            adapter="fake",
            recipient="demo@example.test",
            subject="Synthetic notice",
            text_body="Synthetic content",
            status=EmailExecution.Status.FAILED,
            first_attempt_at=timezone.now() - timedelta(minutes=2),
            attempt_count=1,
            last_error_code="timeout",
        )
        self.client = APIClient()

    def test_staff_cannot_view_or_retry_admin_integration_history(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/api/v1/integrations/status/").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/integrations/executions/").status_code, 403)
        self.assertEqual(
            self.client.post(
                f"/api/v1/integrations/executions/{self.execution.pk}/retry/"
            ).status_code,
            403,
        )

    @override_settings(INTEGRATION_ADAPTER="fake", DEMO_MODE=True)
    def test_admin_can_view_history_and_queue_only_a_safe_retry(self):
        self.client.force_login(self.admin)
        status = self.client.get("/api/v1/integrations/status/")
        history = self.client.get("/api/v1/integrations/executions/")
        retry = self.client.post(f"/api/v1/integrations/executions/{self.execution.pk}/retry/")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["adapter"], "fake")
        self.assertFalse(status.json()["live_ready"])
        self.assertEqual(history.json()["count"], 1)
        self.assertEqual(retry.status_code, 200)
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.status, EmailExecution.Status.PENDING)

    def test_admin_cannot_retry_a_permanent_failure_or_expired_safe_window(self):
        self.client.force_login(self.admin)
        self.execution.last_error_code = "provider_rejected"
        self.execution.save(update_fields=["last_error_code"])
        permanent = self.client.post(f"/api/v1/integrations/executions/{self.execution.pk}/retry/")
        self.execution.last_error_code = "timeout"
        self.execution.first_attempt_at = timezone.now() - timedelta(hours=24)
        self.execution.save(update_fields=["last_error_code", "first_attempt_at"])
        expired = self.client.post(f"/api/v1/integrations/executions/{self.execution.pk}/retry/")
        self.assertEqual(permanent.status_code, 400)
        self.assertEqual(expired.status_code, 400)

    @override_settings(INTEGRATION_ADAPTER="fake", DEMO_MODE=True)
    def test_demo_hides_live_adapter_labels_and_never_runs_a_resend_row(self):
        self.client.force_login(self.admin)
        self.execution.adapter = "resend"
        self.execution.status = EmailExecution.Status.PENDING
        self.execution.next_attempt_at = timezone.now()
        self.execution.save(update_fields=["adapter", "status", "next_attempt_at"])

        history = self.client.get("/api/v1/integrations/executions/")
        with patch("integrations.jobs.ResendEmailAdapter.send") as live_send:
            self.assertEqual(process_due(), 1)

        self.assertEqual(history.json()["results"][0]["adapter"], "fake")
        live_send.assert_not_called()
