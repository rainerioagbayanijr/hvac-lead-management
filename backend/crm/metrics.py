"""Dashboard metrics with explicit time windows and denominators."""

from datetime import timedelta
from decimal import Decimal
from statistics import median

from django.db.models import Count, Sum
from django.utils import timezone

from crm.models import FollowUpTask, Lead


def dashboard_metrics():
    now = timezone.now()
    last_30_days = now - timedelta(days=30)
    mature_start = now - timedelta(days=120)
    mature_end = now - timedelta(days=30)

    pipeline = {stage: 0 for stage, _label in Lead.Stage.choices}
    active_leads = Lead.objects.filter(archived_at__isnull=True)
    pipeline.update(
        active_leads.values("stage").annotate(total=Count("id")).values_list("stage", "total")
    )

    recent = active_leads.filter(received_at__gte=last_30_days)
    response_durations = [
        (contact - received).total_seconds()
        for received, contact in recent.exclude(first_contact_at__isnull=True).values_list(
            "received_at", "first_contact_at"
        )
        if contact >= received
    ]
    mature = active_leads.filter(received_at__gte=mature_start, received_at__lt=mature_end)
    mature_count = mature.count()
    won_count = mature.filter(stage=Lead.Stage.WON).count()
    quote_total = active_leads.filter(stage=Lead.Stage.QUOTED).aggregate(total=Sum("quote_amount"))[
        "total"
    ] or Decimal("0.00")

    return {
        "generated_at": now,
        "pipeline": pipeline,
        "new_leads_30d": recent.count(),
        "awaiting_first_contact": active_leads.filter(
            stage__in=[Lead.Stage.NEW, Lead.Stage.CONTACTED], first_contact_at__isnull=True
        ).count(),
        "overdue_followups": FollowUpTask.objects.filter(
            status=FollowUpTask.Status.PENDING, due_at__lt=now
        ).count(),
        "open_quoted_value_sgd": f"{quote_total:.2f}",
        "response_time_30d": {
            "median_seconds": median(response_durations) if response_durations else None,
            "responded_count": len(response_durations),
            "eligible_count": recent.count(),
        },
        "mature_cohort_win_rate_90d": {
            "won_count": won_count,
            "eligible_count": mature_count,
            "rate": won_count / mature_count if mature_count else None,
            "cohort_start": mature_start,
            "cohort_end": mature_end,
        },
    }
