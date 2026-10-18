import re
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Lead(models.Model):
    class Stage(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        QUOTED = "quoted", "Quoted"
        WON = "won", "Won"
        LOST = "lost", "Lost"

    class Service(models.TextChoices):
        INSTALLATION = "installation", "Installation"
        MAINTENANCE = "maintenance", "Maintenance"
        REPAIR = "repair", "Repair"

    class Source(models.TextChoices):
        WEBSITE = "website", "Website"
        PHONE = "phone", "Phone"
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"
        REFERRAL = "referral", "Referral"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=40, blank=True, default="")
    normalized_phone = models.CharField(max_length=40, blank=True, default="", editable=False)
    email = models.EmailField(blank=True, default="")
    location = models.CharField(max_length=250, blank=True, default="")
    service_type = models.CharField(max_length=20, choices=Service.choices)
    requirements = models.TextField(max_length=4000, blank=True, default="")
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.WEBSITE)
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.NEW)
    first_contact_at = models.DateTimeField(null=True, blank=True)
    quote_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    loss_reason = models.CharField(max_length=500, blank=True, default="")
    closed_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    demo_seeded = models.BooleanField(default=False, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="owned_leads",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="created_leads",
    )
    received_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1, editable=False)
    submission_key = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    request_fingerprint = models.CharField(max_length=64, blank=True, default="", editable=False)

    class Meta:
        ordering = ["-received_at", "-id"]
        indexes = [
            models.Index(fields=["stage", "received_at"], name="lead_stage_received_idx"),
            models.Index(fields=["owner", "stage"], name="lead_owner_stage_idx"),
            models.Index(fields=["source"], name="lead_source_idx"),
            models.Index(fields=["archived_at", "received_at"], name="lead_archive_received_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(name__regex=r"\S"), name="lead_name_not_blank"
            ),
            models.CheckConstraint(
                condition=models.Q(phone__regex=r"\S") | models.Q(email__regex=r"\S"),
                name="lead_contact_required",
            ),
            models.CheckConstraint(
                condition=models.Q(stage__in=["new", "contacted", "quoted", "won", "lost"]),
                name="lead_stage_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(service_type__in=["installation", "maintenance", "repair"]),
                name="lead_service_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    source__in=["website", "phone", "email", "whatsapp", "referral", "other"]
                ),
                name="lead_source_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1), name="lead_version_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(quote_amount__isnull=True) | models.Q(quote_amount__gt=0),
                name="lead_quote_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(stage="lost", loss_reason__regex=r"\S")
                    | (~models.Q(stage="lost") & models.Q(loss_reason=""))
                ),
                name="lead_loss_reason_matches_stage",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(stage__in=["won", "lost"], closed_at__isnull=False)
                    | models.Q(stage__in=["new", "contacted", "quoted"], closed_at__isnull=True)
                ),
                name="lead_closed_time_matches_stage",
            ),
            models.CheckConstraint(
                condition=(~models.Q(stage__in=["quoted", "won"]) | models.Q(quote_amount__gt=0)),
                name="lead_quoted_stage_has_quote",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(submission_key__isnull=True, request_fingerprint="")
                    | models.Q(
                        submission_key__isnull=False, request_fingerprint__regex=r"^[a-f0-9]{64}$"
                    )
                ),
                name="lead_submission_fingerprint_valid",
            ),
        ]

    def clean_fields(self, exclude=None):
        # Normalize before EmailField validates; Model.clean runs after field validation.
        self.name = (self.name or "").strip()
        self.phone = (self.phone or "").strip()
        self.email = (self.email or "").strip().lower()
        self.normalized_phone = re.sub(r"\D", "", self.phone)
        super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        if self.phone and not self.normalized_phone:
            raise ValidationError({"phone": "Enter a phone number containing digits."})
        if self.received_at is None:
            return  # Field validation already reports the missing required timestamp.
        if timezone.is_naive(self.received_at):
            raise ValidationError({"received_at": "Use a time-zone-aware receipt time."})
        if self.received_at > timezone.now():
            raise ValidationError({"received_at": "Receipt time cannot be in the future."})

    def save(self, *args, **kwargs):
        # These identify the original submission, even after staff edit lead details.
        if not self._state.adding:
            original = (
                type(self)
                .objects.filter(pk=self.pk)
                .values("submission_key", "request_fingerprint")
                .first()
            )
            if original and (
                original["submission_key"] != self.submission_key
                or original["request_fingerprint"] != self.request_fingerprint
            ):
                raise ValidationError("Original submission identity cannot be changed.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} — {self.get_service_type_display()}"


class ActivityEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activity")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT
    )
    event_type = models.CharField(max_length=40, default="created")
    occurred_at = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict)
    action_key = models.UUIDField(null=True, blank=True)
    request_fingerprint = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [models.Index(fields=["lead", "occurred_at"], name="activity_lead_time_idx")]
        constraints = [
            models.UniqueConstraint(
                fields=["lead", "action_key"],
                condition=models.Q(action_key__isnull=False),
                name="activity_lead_action_key_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(action_key__isnull=True, request_fingerprint="")
                    | models.Q(
                        action_key__isnull=False,
                        request_fingerprint__regex=r"^[a-f0-9]{64}$",
                    )
                ),
                name="activity_action_fingerprint_valid",
            ),
        ]


class FollowUpTask(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="tasks")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_followups"
    )
    title = models.CharField(max_length=120)
    details = models.CharField(max_length=500, blank=True, default="")
    due_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_at", "id"]
        indexes = [
            models.Index(fields=["status", "due_at"], name="task_status_due_idx"),
            models.Index(fields=["lead", "status", "due_at"], name="task_lead_status_due_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(title__regex=r"\S"), name="task_title_not_blank"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="pending", completed_at__isnull=True, cancelled_at__isnull=True)
                    | models.Q(
                        status="completed", completed_at__isnull=False, cancelled_at__isnull=True
                    )
                    | models.Q(
                        status="cancelled", completed_at__isnull=True, cancelled_at__isnull=False
                    )
                ),
                name="task_status_timestamps_match",
            ),
        ]

    def __str__(self):
        return f"{self.title} — {self.lead.name}"
