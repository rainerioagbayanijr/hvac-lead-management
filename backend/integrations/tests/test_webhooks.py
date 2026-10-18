import base64
import hashlib
import hmac
import json
import time
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from crm.models import Lead
from integrations.fake_adapter import SendResult
from integrations.jobs import process_due
from integrations.models import EmailExecution, WebhookReceipt


def signed_headers(body, secret, event_id="msg_test_1", timestamp=None):
    timestamp = str(timestamp or int(time.time()))
    key = base64.b64decode(secret.removeprefix("whsec_"))
    signed = b".".join((event_id.encode(), timestamp.encode(), body))
    signature = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    return {
        "HTTP_SVIX_ID": event_id,
        "HTTP_SVIX_TIMESTAMP": timestamp,
        "HTTP_SVIX_SIGNATURE": f"v1,{signature}",
    }


class ResendWebhookTests(TestCase):
    secret = "whsec_" + base64.b64encode(b"synthetic-webhook-key").decode()

    def setUp(self):
        self.client = APIClient()
        self.lead = Lead.objects.create(
            name="Synthetic HVAC customer", email="customer@example.test", service_type="repair"
        )
        self.execution = EmailExecution.objects.create(
            lead=self.lead,
            adapter="resend",
            recipient="office@example.test",
            subject="New repair inquiry",
            text_body=f"Reference: {self.lead.pk}",
            status=EmailExecution.Status.ACCEPTED,
            provider_message_id="provider-email-1",
        )

    def send_event(
        self, event_type, event_id="msg_test_1", *, email_id="provider-email-1", created_at=None
    ):
        body = json.dumps(
            {
                "type": event_type,
                "created_at": created_at or timezone.now().isoformat(),
                "data": {"email_id": email_id},
            },
            separators=(",", ":"),
        ).encode()
        return self.client.post(
            "/api/v1/integrations/resend/webhook/",
            data=body,
            content_type="application/json",
            **signed_headers(body, self.secret, event_id),
        )

    @override_settings(RESEND_WEBHOOK_SECRET=secret)
    def test_valid_delivery_is_recorded_and_duplicate_event_is_ignored(self):
        first = self.send_event("email.delivered")
        duplicate = self.send_event("email.delivered")
        self.assertEqual(first.status_code, 202)
        self.assertEqual(duplicate.status_code, 200)
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.status, EmailExecution.Status.DELIVERED)
        self.assertEqual(WebhookReceipt.objects.count(), 1)

    @override_settings(RESEND_WEBHOOK_SECRET=secret)
    def test_invalid_signature_and_stale_timestamp_are_rejected(self):
        raw = b'{"type":"email.delivered","data":{"email_id":"provider-email-1"}}'
        invalid = self.client.post(
            "/api/v1/integrations/resend/webhook/",
            data=raw,
            content_type="application/json",
            HTTP_SVIX_ID="msg_bad",
            HTTP_SVIX_TIMESTAMP=str(int(time.time())),
            HTTP_SVIX_SIGNATURE="v1,invalid",
        )
        stale_headers = signed_headers(
            raw, self.secret, event_id="msg_stale", timestamp=int(time.time()) - 600
        )
        stale = self.client.post(
            "/api/v1/integrations/resend/webhook/",
            data=raw,
            content_type="application/json",
            **stale_headers,
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(stale.status_code, 400)
        self.assertEqual(WebhookReceipt.objects.count(), 0)

    @override_settings(RESEND_WEBHOOK_SECRET=secret)
    def test_out_of_order_sent_event_does_not_regress_delivered_state(self):
        self.send_event("email.delivered", event_id="msg_delivery")
        self.send_event("email.sent", event_id="msg_sent")
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.status, EmailExecution.Status.DELIVERED)
        self.assertEqual(WebhookReceipt.objects.count(), 2)

    @override_settings(RESEND_WEBHOOK_SECRET=secret)
    def test_early_delivery_is_reconciled_after_send_response(self):
        self.execution.status = EmailExecution.Status.PENDING
        self.execution.provider_message_id = ""
        self.execution.next_attempt_at = timezone.now() - timedelta(seconds=1)
        self.execution.save()
        self.execution.refresh_from_db()
        result = self.send_event(
            "email.delivered", event_id="msg_early", email_id="provider-email-2"
        )
        self.assertEqual(result.status_code, 202)
        with override_settings(INTEGRATION_ADAPTER="fake"):
            from unittest.mock import patch

            with patch(
                "integrations.jobs.ResendEmailAdapter.send",
                return_value=SendResult("provider-email-2"),
            ):
                process_due()
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.status, EmailExecution.Status.DELIVERED)
        self.assertEqual(self.execution.provider_message_id, "provider-email-2")

    @override_settings(RESEND_WEBHOOK_SECRET=secret)
    def test_early_bounce_is_not_mistaken_for_delivery(self):
        self.execution.status = EmailExecution.Status.PENDING
        self.execution.provider_message_id = ""
        self.execution.next_attempt_at = timezone.now() - timedelta(seconds=1)
        self.execution.save()
        self.send_event("email.bounced", event_id="msg_bounce_early", email_id="provider-email-2")
        from unittest.mock import patch

        with patch(
            "integrations.jobs.ResendEmailAdapter.send",
            return_value=SendResult("provider-email-2"),
        ):
            process_due()
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.status, EmailExecution.Status.FAILED)
        self.assertEqual(self.execution.last_error_code, "email_bounced")
