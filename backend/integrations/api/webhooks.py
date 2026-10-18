import base64
import binascii
import hashlib
import hmac
import json
import time

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.models import EmailExecution, WebhookReceipt


def valid_signature(raw_body, headers, secret, now=None):
    webhook_id = headers.get("svix-id", "")
    timestamp = headers.get("svix-timestamp", "")
    signatures = headers.get("svix-signature", "")
    if not webhook_id or not timestamp or not signatures or not secret.startswith("whsec_"):
        return False
    try:
        timestamp_number = int(timestamp)
        key = base64.b64decode(secret.removeprefix("whsec_"), validate=True)
    except (ValueError, binascii.Error):
        return False
    current_time = now if now is not None else time.time()
    if abs(current_time - timestamp_number) > 300:
        return False
    signed_content = b".".join((webhook_id.encode(), timestamp.encode(), raw_body))
    digest = base64.b64encode(hmac.new(key, signed_content, hashlib.sha256).digest()).decode()
    return any(
        hmac.compare_digest(signature, digest)
        for versioned in signatures.split()
        for version, separator, signature in [versioned.partition(",")]
        if separator and version == "v1"
    )


def apply_receipt(receipt):
    event_type = receipt.event_type
    execution = receipt.execution
    if execution is None:
        return
    now = timezone.now()
    if event_type == "email.delivered":
        execution.status = EmailExecution.Status.DELIVERED
        execution.delivered_at = receipt.occurred_at or now
    elif event_type in {"email.bounced", "email.complained", "email.failed"}:
        if execution.status != EmailExecution.Status.DELIVERED:
            execution.status = EmailExecution.Status.FAILED
            execution.last_error_code = event_type.replace(".", "_")
            execution.last_error_message = "Email provider reported a delivery failure."
    elif event_type == "email.sent" and execution.status not in {
        EmailExecution.Status.DELIVERED,
        EmailExecution.Status.FAILED,
    }:
        execution.status = EmailExecution.Status.ACCEPTED
        execution.accepted_at = execution.accepted_at or receipt.occurred_at or now
    execution.provider_message_id = receipt.provider_message_id or execution.provider_message_id
    execution.lease_token = None
    execution.lease_expires_at = None
    execution.save(
        update_fields=[
            "status",
            "delivered_at",
            "accepted_at",
            "provider_message_id",
            "last_error_code",
            "last_error_message",
            "lease_token",
            "lease_expires_at",
            "updated_at",
        ]
    )


@method_decorator(csrf_exempt, name="dispatch")
class ResendWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = []
    http_method_names = ["post", "options"]

    def post(self, request):
        raw_body = request._request.body
        headers = {
            "svix-id": request.headers.get("svix-id", ""),
            "svix-timestamp": request.headers.get("svix-timestamp", ""),
            "svix-signature": request.headers.get("svix-signature", ""),
        }
        if not valid_signature(raw_body, headers, settings.RESEND_WEBHOOK_SECRET):
            return Response({"status": "invalid_signature"}, status=400)
        try:
            payload = json.loads(raw_body)
            event_type = payload["type"]
            data = payload["data"]
            provider_message_id = data.get("email_id", "")
            occurred_at = parse_datetime(payload.get("created_at", ""))
            event_id = headers["svix-id"]
            if not isinstance(event_type, str) or not isinstance(provider_message_id, str):
                raise ValueError
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return Response({"status": "invalid_payload"}, status=400)

        execution = EmailExecution.objects.filter(provider_message_id=provider_message_id).first()
        try:
            with transaction.atomic():
                receipt = WebhookReceipt.objects.create(
                    provider_event_id=event_id,
                    execution=execution,
                    event_type=event_type[:80],
                    provider_message_id=provider_message_id[:120],
                    occurred_at=occurred_at,
                )
                apply_receipt(receipt)
        except IntegrityError:
            return Response({"status": "duplicate"}, status=200)
        return Response({"status": "recorded"}, status=202)
