from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from integrations.models import EmailExecution


def enqueue_inquiry_notification(lead):
    adapter = "fake" if settings.DEMO_MODE else settings.INTEGRATION_ADAPTER
    if adapter not in {"fake", "resend"}:
        raise ImproperlyConfigured("INTEGRATION_ADAPTER must be fake or resend.")
    recipient = settings.INQUIRY_NOTIFICATION_EMAIL or "demo@example.test"
    service = lead.get_service_type_display()
    return EmailExecution.objects.create(
        lead=lead,
        adapter=adapter,
        recipient=recipient,
        subject=f"New {service.lower()} inquiry",
        text_body=(
            f"A new {service.lower()} inquiry was received.\n"
            f"Reference: {lead.pk}\n"
            "Open the staff workspace to assign an owner and follow up."
        ),
    )


def request_manual_retry(execution):
    from datetime import timedelta

    from django.db import transaction
    from django.utils import timezone
    from rest_framework.exceptions import ValidationError

    with transaction.atomic():
        current = EmailExecution.objects.select_for_update().get(pk=execution.pk)
        now = timezone.now()
        safe_until = (
            current.first_attempt_at + timedelta(hours=23) if current.first_attempt_at else now
        )
        if (
            current.status != EmailExecution.Status.FAILED
            or current.attempt_count >= 5
            or current.last_error_code not in {"temporary_failure", "timeout", "rate_limited"}
            or now >= safe_until
        ):
            raise ValidationError({"retry": ["This alert is not safe to retry automatically."]})
        current.status = EmailExecution.Status.PENDING
        current.next_attempt_at = now
        current.lease_token = None
        current.lease_expires_at = None
        current.save(
            update_fields=[
                "status",
                "next_attempt_at",
                "lease_token",
                "lease_expires_at",
                "updated_at",
            ]
        )
        return current
