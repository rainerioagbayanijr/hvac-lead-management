import uuid

from django.db import models
from django.utils import timezone

from crm.models import Lead


class EmailExecution(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        ACCEPTED = "accepted", "Accepted"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        REVIEW = "review", "Needs review"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="email_executions")
    event_type = models.CharField(max_length=40, default="inquiry_notification")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    adapter = models.CharField(max_length=12, choices=[("fake", "Fake"), ("resend", "Resend")])
    recipient = models.EmailField()
    subject = models.CharField(max_length=180)
    text_body = models.CharField(max_length=1000)
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    provider_message_id = models.CharField(max_length=120, blank=True, default="")
    attempt_count = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    first_attempt_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=80, blank=True, default="")
    last_error_message = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "next_attempt_at"], name="email_due_status_idx"),
            models.Index(fields=["lead", "created_at"], name="email_lead_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(attempt_count__lte=5), name="email_attempt_limit"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "pending",
                        "processing",
                        "accepted",
                        "delivered",
                        "failed",
                        "review",
                    ]
                ),
                name="email_status_valid",
            ),
        ]


class EmailAttempt(models.Model):
    class Status(models.TextChoices):
        STARTED = "started", "Started"
        ACCEPTED = "accepted", "Accepted"
        RETRY = "retry", "Retry scheduled"
        FAILED = "failed", "Failed"
        UNCERTAIN = "uncertain", "Uncertain outcome"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    execution = models.ForeignKey(EmailExecution, on_delete=models.CASCADE, related_name="attempts")
    attempt_number = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.STARTED)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=80, blank=True, default="")
    error_message = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["attempt_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["execution", "attempt_number"], name="email_attempt_number_unique"
            )
        ]


class WebhookReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider_event_id = models.CharField(max_length=160, unique=True)
    execution = models.ForeignKey(
        EmailExecution,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="webhook_receipts",
    )
    event_type = models.CharField(max_length=80)
    provider_message_id = models.CharField(max_length=120, blank=True, default="")
    occurred_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["execution", "received_at"], name="webhook_exec_received_idx")
        ]


class WorkerHeartbeat(models.Model):
    worker_name = models.CharField(max_length=40, unique=True, default="email-executions")
    last_started_at = models.DateTimeField(null=True, blank=True)
    last_finished_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_processed_count = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=300, blank=True, default="")
