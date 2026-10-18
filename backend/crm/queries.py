"""Read-only CRM queries shared by the API and dashboard."""

from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import User
from crm.models import FollowUpTask, Lead


def filtered_leads(params, user):
    queryset = Lead.objects.select_related("owner").prefetch_related("tasks").all()
    archived = params.get("archived", "").strip()
    if archived:
        if user.role != User.Role.ADMIN or archived != "true":
            raise ValidationError(
                {"archived": ["Archived inquiries are available to admins only."]}
            )
        queryset = queryset.filter(archived_at__isnull=False)
    else:
        queryset = queryset.filter(archived_at__isnull=True)
    query = params.get("q", "").strip()
    if len(query) > 120:
        raise ValidationError({"q": ["Search text must be 120 characters or fewer."]})
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
            | Q(location__icontains=query)
        )

    for key, field, choices in (
        ("stage", "stage", Lead.Stage.values),
        ("source", "source", Lead.Source.values),
        ("service", "service_type", Lead.Service.values),
    ):
        value = params.get(key, "").strip()
        if value:
            if value not in choices:
                raise ValidationError({key: ["Choose a valid filter option."]})
            queryset = queryset.filter(**{field: value})

    owner = params.get("owner", "").strip()
    if owner == "mine":
        queryset = queryset.filter(owner_id=user.pk)
    elif owner == "unassigned":
        queryset = queryset.filter(owner__isnull=True)
    elif owner:
        if user.role != User.Role.ADMIN or not owner.isdecimal():
            raise ValidationError({"owner": ["Choose mine or unassigned."]})
        queryset = queryset.filter(owner_id=int(owner))

    due = params.get("due", "").strip()
    if due:
        if due != "overdue":
            raise ValidationError({"due": ["Choose overdue."]})
        queryset = queryset.filter(
            tasks__status=FollowUpTask.Status.PENDING,
            tasks__due_at__lt=timezone.now(),
        ).distinct()
    return queryset.order_by("-received_at", "-id")
