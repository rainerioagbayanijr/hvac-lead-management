import hashlib
import json

from django.core.exceptions import ValidationError as ModelValidationError
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from config.api import Conflict
from integrations.services import enqueue_inquiry_notification

from .models import ActivityEvent, Lead


def create_inquiry(values):
    """Atomically store the inquiry/history, or replay its original reference."""
    values = values.copy()
    key = values.pop("submission_key")
    values.pop("company_website", None)
    values.pop("privacy_acknowledged")
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def replay(existing):
        if existing.request_fingerprint != fingerprint:
            raise Conflict()
        return existing, False

    existing = Lead.objects.filter(submission_key=key).first()
    if existing:
        return replay(existing)

    try:
        with transaction.atomic():
            lead = Lead(**values, submission_key=key, request_fingerprint=fingerprint)
            # Uniqueness is enforced by PostgreSQL below, including simultaneous requests.
            lead.full_clean(validate_unique=False, validate_constraints=False)
            lead.save(force_insert=True)
            ActivityEvent.objects.create(
                lead=lead,
                metadata={"source": "website", "privacy_notice_version": "1"},
            )
            enqueue_inquiry_notification(lead)
    except ModelValidationError as exc:
        raise ValidationError(exc.message_dict) from exc
    except IntegrityError:
        # Query only after the failed transaction has rolled back.
        existing = Lead.objects.filter(submission_key=key).first()
        if existing:
            return replay(existing)
        raise
    return lead, True
