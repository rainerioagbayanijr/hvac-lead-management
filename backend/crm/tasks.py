from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from .models import FollowUpTask, Lead
from .workflow import _mutate


def _task_for_lead(lead, task_id):
    try:
        return FollowUpTask.objects.get(lead=lead, pk=task_id)
    except FollowUpTask.DoesNotExist as exc:
        raise NotFound("The follow-up task is unavailable.") from exc


def _require_pending(task):
    if task.status != FollowUpTask.Status.PENDING:
        raise ValidationError({"task": ["Only pending follow-ups can be changed."]})


def schedule_task(lead_id, actor, action_key, expected_version, title, details, due_at):
    def change(lead):
        if lead.stage in [Lead.Stage.WON, Lead.Stage.LOST]:
            raise ValidationError({"lead": ["Reopen this lead before scheduling follow-up."]})
        task = FollowUpTask.objects.create(
            lead=lead,
            created_by=actor,
            title=title.strip(),
            details=details.strip(),
            due_at=due_at,
        )
        return (
            "task_scheduled",
            {"task_id": str(task.pk), "title": task.title, "due_at": task.due_at.isoformat()},
            [],
        )

    return _mutate(
        lead_id,
        actor,
        action_key,
        expected_version,
        "task_schedule",
        {"title": title.strip(), "details": details.strip(), "due_at": due_at},
        change,
    )


def reschedule_task(lead_id, task_id, actor, action_key, expected_version, due_at):
    def change(lead):
        task = _task_for_lead(lead, task_id)
        _require_pending(task)
        old_due = task.due_at
        task.due_at = due_at
        task.save(update_fields=["due_at", "updated_at"])
        return (
            "task_rescheduled",
            {
                "task_id": str(task.pk),
                "title": task.title,
                "previous_due_at": old_due.isoformat(),
                "due_at": task.due_at.isoformat(),
            },
            [],
        )

    return _mutate(
        lead_id,
        actor,
        action_key,
        expected_version,
        "task_reschedule",
        {"task_id": task_id, "due_at": due_at},
        change,
    )


def complete_task(lead_id, task_id, actor, action_key, expected_version):
    def change(lead):
        task = _task_for_lead(lead, task_id)
        _require_pending(task)
        task.status = FollowUpTask.Status.COMPLETED
        task.completed_at = timezone.now()
        task.save(update_fields=["status", "completed_at", "updated_at"])
        return (
            "task_completed",
            {"task_id": str(task.pk), "title": task.title},
            [],
        )

    return _mutate(
        lead_id,
        actor,
        action_key,
        expected_version,
        "task_complete",
        {"task_id": task_id},
        change,
    )


def cancel_task(lead_id, task_id, actor, action_key, expected_version):
    def change(lead):
        task = _task_for_lead(lead, task_id)
        _require_pending(task)
        task.status = FollowUpTask.Status.CANCELLED
        task.cancelled_at = timezone.now()
        task.save(update_fields=["status", "cancelled_at", "updated_at"])
        return (
            "task_cancelled",
            {"task_id": str(task.pk), "title": task.title},
            [],
        )

    return _mutate(
        lead_id,
        actor,
        action_key,
        expected_version,
        "task_cancel",
        {"task_id": task_id},
        change,
    )
