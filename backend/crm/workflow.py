import hashlib
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from config.api import Conflict

from .models import ActivityEvent, FollowUpTask, Lead

User = get_user_model()


def _fingerprint(kind, actor, payload):
    canonical = json.dumps(
        {"kind": kind, "actor": actor.pk, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_admin(actor):
    return actor.role == User.Role.ADMIN


def _can_change(actor, lead):
    return _is_admin(actor) or (actor.role == User.Role.STAFF and lead.owner_id == actor.pk)


def _mutate(lead_id, actor, action_key, expected_version, kind, payload, change):
    fingerprint = _fingerprint(kind, actor, payload)
    with transaction.atomic():
        try:
            lead = Lead.objects.select_for_update().get(pk=lead_id)
        except Lead.DoesNotExist as exc:
            raise NotFound("The lead is unavailable.") from exc

        existing = ActivityEvent.objects.filter(lead=lead, action_key=action_key).first()
        if existing:
            if existing.actor_id != actor.pk or existing.request_fingerprint != fingerprint:
                raise Conflict(
                    "This action key was already used for a different request.", code="conflict"
                )
            return lead

        if lead.version != expected_version:
            raise Conflict("This lead changed. Refresh it and try again.", code="conflict")
        if lead.archived_at and kind not in {"archive", "restore"}:
            raise ValidationError({"lead": ["Restore this lead before making changes."]})
        can_claim = kind == "claim" and actor.role in [User.Role.STAFF, User.Role.ADMIN]
        if not _can_change(actor, lead) and not can_claim:
            raise PermissionDenied("You can change only leads assigned to you.")

        event_type, metadata, update_fields = change(lead)
        lead.version += 1
        lead.save(update_fields=[*update_fields, "version", "updated_at"])
        ActivityEvent.objects.create(
            lead=lead,
            actor=actor,
            event_type=event_type,
            metadata=metadata,
            action_key=action_key,
            request_fingerprint=fingerprint,
        )
        return lead


def claim_lead(lead_id, actor, action_key, expected_version):
    def change(lead):
        if lead.stage in [Lead.Stage.WON, Lead.Stage.LOST]:
            raise ValidationError({"lead": ["Closed leads cannot be claimed."]})
        if lead.owner_id is not None:
            raise Conflict("Another staff member already owns this lead.", code="conflict")
        lead.owner = actor
        return "claimed", {"owner_name": actor.display_name}, ["owner"]

    return _mutate(lead_id, actor, action_key, expected_version, "claim", {}, change)


def assign_lead(lead_id, actor, action_key, expected_version, owner_id):
    if not _is_admin(actor):
        raise PermissionDenied("Only an admin can assign leads.")
    if owner_id is None:
        owner = None
    else:
        owner = User.objects.filter(pk=owner_id, is_active=True).first()
        if owner is None:
            raise ValidationError({"owner_id": ["Choose an active team member."]})

    def change(lead):
        previous = lead.owner.display_name if lead.owner_id else None
        if lead.owner_id == (owner.pk if owner else None):
            raise ValidationError({"owner_id": ["Choose a different owner."]})
        lead.owner = owner
        return (
            "assigned",
            {
                "previous_owner": previous,
                "owner_name": owner.display_name if owner else None,
            },
            ["owner"],
        )

    return _mutate(
        lead_id,
        actor,
        action_key,
        expected_version,
        "assignment",
        {"owner_id": owner.pk if owner else None},
        change,
    )


def record_contact(lead_id, actor, action_key, expected_version, method, summary):
    def change(lead):
        if lead.stage in [Lead.Stage.WON, Lead.Stage.LOST]:
            raise ValidationError({"stage": ["Reopen this lead before recording contact."]})
        now = timezone.now()
        first_contact = lead.first_contact_at is None
        if first_contact:
            lead.first_contact_at = now
        previous_stage = lead.stage
        if lead.stage == Lead.Stage.NEW:
            lead.stage = Lead.Stage.CONTACTED
        metadata = {
            "method": method,
            "summary": summary,
            "first_contact": first_contact,
            "stage_from": previous_stage,
            "stage_to": lead.stage,
        }
        return "contact_recorded", metadata, ["first_contact_at", "stage"]

    return _mutate(
        lead_id,
        actor,
        action_key,
        expected_version,
        "contact",
        {"method": method, "summary": summary},
        change,
    )


def change_stage(lead_id, actor, action_key, expected_version, stage, quote_amount, loss_reason):
    def change(lead):
        current = lead.stage
        if current in [Lead.Stage.WON, Lead.Stage.LOST]:
            raise ValidationError({"stage": ["Reopen this lead before changing its stage."]})
        if stage == Lead.Stage.LOST:
            reason = loss_reason.strip()
            if not reason:
                raise ValidationError({"loss_reason": ["Explain why this lead was lost."]})
            lead.stage = stage
            lead.loss_reason = reason
            lead.closed_at = timezone.now()
            cancelled_count = FollowUpTask.objects.filter(
                lead=lead, status=FollowUpTask.Status.PENDING
            ).update(
                status=FollowUpTask.Status.CANCELLED,
                cancelled_at=timezone.now(),
                updated_at=timezone.now(),
            )
            return (
                "stage_changed",
                {
                    "stage_from": current,
                    "stage_to": stage,
                    "loss_reason": reason,
                    "cancelled_tasks": cancelled_count,
                },
                ["stage", "loss_reason", "closed_at"],
            )

        allowed = {
            Lead.Stage.NEW: {Lead.Stage.CONTACTED},
            Lead.Stage.CONTACTED: {Lead.Stage.QUOTED},
            Lead.Stage.QUOTED: {Lead.Stage.WON},
        }
        if stage not in allowed.get(current, set()):
            raise ValidationError({"stage": ["That stage change is not allowed."]})
        update_fields = ["stage"]
        metadata = {"stage_from": current, "stage_to": stage}
        if stage == Lead.Stage.QUOTED:
            if quote_amount is None:
                raise ValidationError({"quote_amount": ["Enter the quoted amount in SGD."]})
            lead.quote_amount = Decimal(quote_amount)
            metadata["quote_amount"] = str(lead.quote_amount)
            update_fields.append("quote_amount")
        if stage == Lead.Stage.WON:
            if lead.quote_amount is None:
                raise ValidationError({"quote_amount": ["Record a quote before marking this won."]})
            lead.closed_at = timezone.now()
            update_fields.append("closed_at")
            metadata["cancelled_tasks"] = FollowUpTask.objects.filter(
                lead=lead, status=FollowUpTask.Status.PENDING
            ).update(
                status=FollowUpTask.Status.CANCELLED,
                cancelled_at=timezone.now(),
                updated_at=timezone.now(),
            )
        lead.stage = stage
        return "stage_changed", metadata, update_fields

    payload = {"stage": stage, "quote_amount": quote_amount, "loss_reason": loss_reason}
    return _mutate(lead_id, actor, action_key, expected_version, "stage", payload, change)


def reopen_lead(lead_id, actor, action_key, expected_version, stage):
    if not _is_admin(actor):
        raise PermissionDenied("Only an admin can reopen leads.")

    def change(lead):
        if lead.stage not in [Lead.Stage.WON, Lead.Stage.LOST]:
            raise ValidationError({"stage": ["Only a closed lead can be reopened."]})
        if stage not in [Lead.Stage.NEW, Lead.Stage.CONTACTED, Lead.Stage.QUOTED]:
            raise ValidationError({"stage": ["Choose an open stage."]})
        if stage == Lead.Stage.QUOTED and lead.quote_amount is None:
            raise ValidationError({"stage": ["This lead has no quote to reopen at Quoted."]})
        previous = lead.stage
        lead.stage = stage
        lead.closed_at = None
        lead.loss_reason = ""
        return (
            "lead_reopened",
            {"stage_from": previous, "stage_to": stage},
            ["stage", "closed_at", "loss_reason"],
        )

    return _mutate(
        lead_id,
        actor,
        action_key,
        expected_version,
        "reopen",
        {"stage": stage},
        change,
    )


def add_note(lead_id, actor, action_key, expected_version, body):
    text = body.strip()

    def change(lead):
        if not text:
            raise ValidationError({"body": ["Write a note before saving."]})
        return "note_added", {"body": text}, []

    return _mutate(lead_id, actor, action_key, expected_version, "note", {"body": text}, change)


def archive_lead(lead_id, actor, action_key, expected_version, restore=False):
    if not _is_admin(actor):
        raise PermissionDenied("Only an admin can archive or restore leads.")

    def change(lead):
        now = timezone.now()
        if restore:
            if lead.archived_at is None:
                raise ValidationError({"lead": ["This lead is already active."]})
            lead.archived_at = None
            return "lead_restored", {}, ["archived_at"]
        if lead.archived_at is not None:
            raise ValidationError({"lead": ["This lead is already archived."]})
        lead.archived_at = now
        cancelled_count = FollowUpTask.objects.filter(
            lead=lead, status=FollowUpTask.Status.PENDING
        ).update(
            status=FollowUpTask.Status.CANCELLED,
            cancelled_at=now,
            updated_at=now,
        )
        return "lead_archived", {"cancelled_tasks": cancelled_count}, ["archived_at"]

    kind = "restore" if restore else "archive"
    return _mutate(lead_id, actor, action_key, expected_version, kind, {}, change)


@transaction.atomic
def create_manual_lead(actor, values):
    values = values.copy()
    received_at = values.pop("received_at", None) or timezone.now()
    lead = Lead(
        **values,
        received_at=received_at,
        created_by=actor,
        owner=actor if actor.role == User.Role.STAFF else None,
    )
    try:
        lead.full_clean(validate_unique=False, validate_constraints=False)
    except ModelValidationError as exc:
        raise ValidationError(exc.message_dict) from exc
    lead.save(force_insert=True)
    ActivityEvent.objects.create(
        lead=lead,
        actor=actor,
        event_type="manual_created",
        metadata={"source": lead.source, "received_at": lead.received_at.isoformat()},
    )
    return lead
