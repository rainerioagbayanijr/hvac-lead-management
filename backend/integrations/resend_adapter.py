"""Small Resend REST adapter using Python's standard library."""

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


@dataclass(frozen=True)
class SendResult:
    provider_message_id: str
    http_status: int


class EmailDeliveryError(Exception):
    def __init__(self, code, message, *, retryable, uncertain=False, http_status=None):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.uncertain = uncertain
        self.http_status = http_status


class ResendEmailAdapter:
    endpoint = "https://api.resend.com/emails"

    def send(self, execution):
        if (
            not settings.RESEND_API_KEY
            or not settings.RESEND_FROM_EMAIL
            or execution.recipient.endswith("example.test")
        ):
            raise EmailDeliveryError(
                "configuration_error", "Live email settings are incomplete.", retryable=False
            )
        payload = {
            "from": settings.RESEND_FROM_EMAIL,
            "to": [execution.recipient],
            "subject": execution.subject,
            "text": execution.text_body,
        }
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
                "Idempotency-Key": str(execution.idempotency_key),
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=8) as response:
                body = json.loads(response.read(64_000).decode("utf-8"))
                message_id = body.get("id")
                if not message_id:
                    raise EmailDeliveryError(
                        "invalid_response",
                        "Email provider response had no message ID.",
                        retryable=True,
                        uncertain=True,
                        http_status=response.status,
                    )
                return SendResult(provider_message_id=message_id, http_status=response.status)
        except HTTPError as exc:
            retryable = exc.code == 429 or exc.code >= 500
            raise EmailDeliveryError(
                "rate_limited"
                if exc.code == 429
                else "temporary_failure"
                if retryable
                else "provider_rejected",
                f"Email provider returned HTTP {exc.code}.",
                retryable=retryable,
                uncertain=exc.code >= 500,
                http_status=exc.code,
            ) from exc
        except (TimeoutError, URLError) as exc:
            # A timeout can follow provider acceptance; retry with the same idempotency key.
            raise EmailDeliveryError(
                "timeout",
                "Email provider did not return a timely response.",
                retryable=True,
                uncertain=True,
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise EmailDeliveryError(
                "temporary_failure",
                "Email provider could not be reached or parsed.",
                retryable=True,
                uncertain=True,
            ) from exc
