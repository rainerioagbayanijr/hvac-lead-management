"""Database-backed, leased processing for email notifications."""

from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from integrations.fake_adapter import FakeEmailAdapter
from integrations.models import EmailAttempt, EmailExecution, WebhookReceipt
from integrations.resend_adapter import EmailDeliveryError, ResendEmailAdapter

RETRY_MINUTES = (1, 5, 15, 60)
MAX_ATTEMPTS = 5
SAFE_RETRY_HOURS = 23
LEASE_SECONDS = 60


def adapter_for(execution):
    if settings.DEMO_MODE or execution.adapter == "fake":
        return FakeEmailAdapter()
    if execution.adapter == "resend":
        return ResendEmailAdapter()
    raise ValueError("Unknown email adapter.")


def claim_due(limit=50):
    now = timezone.now()
    claimed = []
    with transaction.atomic():
        due = EmailExecution.objects.filter(
            Q(status=EmailExecution.Status.PENDING, next_attempt_at__lte=now)
            | Q(status=EmailExecution.Status.PROCESSING, lease_expires_at__lte=now)
        ).order_by("next_attempt_at", "created_at")
        for execution in due.select_for_update(skip_locked=True)[:limit]:
            previous_attempt = execution.attempts.filter(status=EmailAttempt.Status.STARTED).first()
            if previous_attempt:
                previous_attempt.status = EmailAttempt.Status.UNCERTAIN
                previous_attempt.finished_at = now
                previous_attempt.error_code = "worker_lease_expired"
                previous_attempt.error_message = "The worker lease expired before completion."
                previous_attempt.save(
                    update_fields=["status", "finished_at", "error_code", "error_message"]
                )

            if execution.first_attempt_at and now >= execution.first_attempt_at + timedelta(
                hours=SAFE_RETRY_HOURS
            ):
                execution.status = EmailExecution.Status.REVIEW
                execution.last_error_code = "safe_window_expired"
                execution.last_error_message = "The provider idempotency window may have expired."
                execution.lease_token = None
                execution.lease_expires_at = None
                execution.save()
                continue
            if execution.attempt_count >= MAX_ATTEMPTS:
                execution.status = EmailExecution.Status.REVIEW
                execution.last_error_code = "attempt_limit"
                execution.last_error_message = "The automatic attempt limit was reached."
                execution.lease_token = None
                execution.lease_expires_at = None
                execution.save()
                continue

            execution.attempt_count += 1
            execution.first_attempt_at = execution.first_attempt_at or now
            execution.status = EmailExecution.Status.PROCESSING
            execution.lease_token = uuid4()
            execution.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
            execution.save()
            attempt = EmailAttempt.objects.create(
                execution=execution,
                attempt_number=execution.attempt_count,
            )
            claimed.append((execution, attempt, execution.lease_token))
    return claimed


def finish_attempt(execution, attempt, lease_token, result=None, error=None):
    now = timezone.now()
    with transaction.atomic():
        current = EmailExecution.objects.select_for_update().get(pk=execution.pk)
        if result:
            attempt.status = EmailAttempt.Status.ACCEPTED
            attempt.http_status = result.http_status
            attempt.finished_at = now
            attempt.save(update_fields=["status", "http_status", "finished_at"])
            current.provider_message_id = result.provider_message_id
            early_receipts = list(
                WebhookReceipt.objects.filter(provider_message_id=result.provider_message_id)
                .exclude(occurred_at__gt=now)
                .order_by("occurred_at")
            )
            current.accepted_at = current.accepted_at or now
            delivered_receipt = next(
                (receipt for receipt in early_receipts if receipt.event_type == "email.delivered"),
                None,
            )
            failed_receipt = next(
                (
                    receipt
                    for receipt in early_receipts
                    if receipt.event_type in {"email.bounced", "email.complained", "email.failed"}
                ),
                None,
            )
            if current.status == EmailExecution.Status.DELIVERED:
                pass
            elif current.status == EmailExecution.Status.FAILED:
                pass
            elif result.delivered_at or delivered_receipt:
                current.status = EmailExecution.Status.DELIVERED
                current.delivered_at = result.delivered_at or delivered_receipt.occurred_at or now
            elif failed_receipt:
                current.status = EmailExecution.Status.FAILED
                current.last_error_code = failed_receipt.event_type.replace(".", "_")
                current.last_error_message = "Email provider reported a delivery failure."
            else:
                current.status = EmailExecution.Status.ACCEPTED
            if current.status != EmailExecution.Status.FAILED:
                current.last_error_code = ""
                current.last_error_message = ""
        else:
            assert error is not None
            attempt.http_status = error.http_status
            attempt.error_code = error.code
            attempt.error_message = str(error)[:300]
            attempt.finished_at = now
            safe_window_open = (
                current.first_attempt_at
                and now < current.first_attempt_at + timedelta(hours=SAFE_RETRY_HOURS)
            )
            can_retry = (
                error.retryable and current.attempt_count < MAX_ATTEMPTS and safe_window_open
            )
            if can_retry:
                attempt.status = (
                    EmailAttempt.Status.UNCERTAIN if error.uncertain else EmailAttempt.Status.RETRY
                )
                delay = RETRY_MINUTES[min(current.attempt_count - 1, len(RETRY_MINUTES) - 1)]
                current.status = EmailExecution.Status.PENDING
                current.next_attempt_at = now + timedelta(minutes=delay)
            else:
                attempt.status = (
                    EmailAttempt.Status.UNCERTAIN if error.uncertain else EmailAttempt.Status.FAILED
                )
                current.status = (
                    EmailExecution.Status.REVIEW
                    if error.uncertain or not safe_window_open and current.first_attempt_at
                    else EmailExecution.Status.FAILED
                )
            attempt.save(
                update_fields=[
                    "status",
                    "http_status",
                    "error_code",
                    "error_message",
                    "finished_at",
                ]
            )
            current.last_error_code = error.code
            current.last_error_message = str(error)[:300]
        if current.lease_token == lease_token:
            current.lease_token = None
            current.lease_expires_at = None
            current.save()


def process_due(limit=50):
    claimed = claim_due(limit=limit)
    for execution, attempt, lease_token in claimed:
        try:
            result = adapter_for(execution).send(execution)
        except EmailDeliveryError as error:
            finish_attempt(execution, attempt, lease_token, error=error)
        except Exception:  # Record a safe retry for adapter or network surprises.
            finish_attempt(
                execution,
                attempt,
                lease_token,
                error=EmailDeliveryError(
                    "temporary_failure",
                    "The email adapter failed unexpectedly.",
                    retryable=True,
                    uncertain=True,
                ),
            )
        else:
            finish_attempt(execution, attempt, lease_token, result=result)
    return len(claimed)
