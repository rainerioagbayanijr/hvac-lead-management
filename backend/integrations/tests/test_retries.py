from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from crm.models import Lead
from integrations.fake_adapter import SendResult
from integrations.jobs import process_due
from integrations.models import EmailAttempt, EmailExecution, WorkerHeartbeat
from integrations.resend_adapter import EmailDeliveryError


class EmailExecutionTests(TestCase):
    def make_execution(self, **values):
        lead = Lead.objects.create(
            name="Synthetic HVAC customer", email="customer@example.test", service_type="repair"
        )
        defaults = {
            "lead": lead,
            "adapter": "resend",
            "recipient": "office@example.test",
            "subject": "New repair inquiry",
            "text_body": f"Reference: {lead.pk}",
            "next_attempt_at": timezone.now(),
        }
        defaults.update(values)
        return EmailExecution.objects.create(**defaults)

    def test_fake_adapter_records_delivery_without_network(self):
        execution = self.make_execution(adapter="fake")
        self.assertEqual(process_due(), 1)
        execution.refresh_from_db()
        self.assertEqual(execution.status, EmailExecution.Status.DELIVERED)
        self.assertEqual(execution.attempt_count, 1)
        self.assertEqual(execution.attempts.get().status, EmailAttempt.Status.ACCEPTED)

    @override_settings(DEMO_MODE=True)
    def test_demo_mode_forces_fake_adapter_even_for_a_resend_execution(self):
        execution = self.make_execution(adapter="resend")
        with patch("integrations.jobs.ResendEmailAdapter.send") as live_send:
            self.assertEqual(process_due(), 1)
        live_send.assert_not_called()
        execution.refresh_from_db()
        self.assertEqual(execution.status, EmailExecution.Status.DELIVERED)

    def test_temporary_failure_retries_same_execution_with_stable_key(self):
        execution = self.make_execution()
        current = timezone.now()
        failure = EmailDeliveryError(
            "timeout", "provider timed out", retryable=True, uncertain=True
        )
        observed_keys = []

        def send(value):
            observed_keys.append(value.idempotency_key)
            if len(observed_keys) == 1:
                raise failure
            return SendResult("provider-email-1")

        with patch("integrations.jobs.ResendEmailAdapter.send", side_effect=send):
            with patch("integrations.jobs.timezone.now", return_value=current):
                self.assertEqual(process_due(), 1)
            execution.refresh_from_db()
            self.assertEqual(execution.status, EmailExecution.Status.PENDING)
            self.assertEqual(execution.next_attempt_at, current + timedelta(minutes=1))
            execution.next_attempt_at = current + timedelta(minutes=1)
            execution.save(update_fields=["next_attempt_at"])
            with patch(
                "integrations.jobs.timezone.now", return_value=current + timedelta(minutes=1)
            ):
                self.assertEqual(process_due(), 1)

        execution.refresh_from_db()
        self.assertEqual(observed_keys, [execution.idempotency_key, execution.idempotency_key])
        self.assertEqual(execution.status, EmailExecution.Status.ACCEPTED)
        self.assertEqual(execution.attempts.count(), 2)

    def test_permanent_provider_rejection_is_not_retried(self):
        execution = self.make_execution()
        failure = EmailDeliveryError(
            "provider_rejected", "invalid sender", retryable=False, http_status=422
        )
        with patch("integrations.jobs.ResendEmailAdapter.send", side_effect=failure):
            self.assertEqual(process_due(), 1)
        execution.refresh_from_db()
        self.assertEqual(execution.status, EmailExecution.Status.FAILED)
        self.assertEqual(execution.attempts.count(), 1)

    def test_expired_provider_idempotency_window_goes_to_review(self):
        current = timezone.now()
        execution = self.make_execution(
            first_attempt_at=current - timedelta(hours=24),
            next_attempt_at=current,
        )
        with patch("integrations.jobs.timezone.now", return_value=current):
            self.assertEqual(process_due(), 0)
        execution.refresh_from_db()
        self.assertEqual(execution.status, EmailExecution.Status.REVIEW)
        self.assertEqual(execution.attempt_count, 0)

    def test_expired_worker_lease_is_reclaimed_and_previous_attempt_marked_uncertain(self):
        current = timezone.now()
        execution = self.make_execution(
            status=EmailExecution.Status.PROCESSING,
            attempt_count=1,
            first_attempt_at=current - timedelta(minutes=2),
            next_attempt_at=current,
            lease_token="b10cf24a-3934-4901-a150-e45b0ddc5862",
            lease_expires_at=current - timedelta(seconds=1),
        )
        old_attempt = EmailAttempt.objects.create(execution=execution, attempt_number=1)
        with patch("integrations.jobs.timezone.now", return_value=current):
            with patch(
                "integrations.jobs.ResendEmailAdapter.send",
                return_value=SendResult("recovered-provider-id"),
            ):
                self.assertEqual(process_due(), 1)
        old_attempt.refresh_from_db()
        execution.refresh_from_db()
        self.assertEqual(old_attempt.status, EmailAttempt.Status.UNCERTAIN)
        self.assertEqual(execution.status, EmailExecution.Status.ACCEPTED)
        self.assertEqual(execution.attempt_count, 2)

    def test_worker_command_records_a_fresh_success(self):
        self.make_execution(adapter="fake")
        from django.core.management import call_command

        call_command("process_email_executions", verbosity=0)
        heartbeat = WorkerHeartbeat.objects.get(worker_name="email-executions")
        self.assertEqual(heartbeat.last_processed_count, 1)
        self.assertIsNotNone(heartbeat.last_success_at)
