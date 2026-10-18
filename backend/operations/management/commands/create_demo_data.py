import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from crm.models import ActivityEvent, FollowUpTask, Lead
from integrations.jobs import process_due
from integrations.models import EmailAttempt, EmailExecution
from integrations.services import enqueue_inquiry_notification

User = get_user_model()


def ensure_demo_user(username, password, role, first_name):
    user = User.objects.filter(username=username).first()
    if user and user.role != role:
        raise CommandError(f"Configured demo account {username} has the wrong role.")
    if user:
        return user
    if len(password) < 12:
        raise CommandError(
            f"Set the password for new demo account {username} to at least 12 characters."
        )
    create = User.objects.create_superuser if role == User.Role.ADMIN else User.objects.create_user
    return create(
        username=username,
        password=password,
        first_name=first_name,
        email=f"{username}@example.test",
        role=role,
    )


def seed_demo_records():
    if Lead.objects.filter(demo_seeded=True).exists():
        return 0
    credentials = [
        ("DEMO_ADMIN_USERNAME", "portfolio_demo_admin", User.Role.ADMIN, "Demo Owner"),
        ("DEMO_STAFF_USERNAME", "portfolio_demo_staff", User.Role.STAFF, "Demo Office"),
        ("DEMO_OTHER_STAFF_USERNAME", "portfolio_demo_other", User.Role.STAFF, "Demo Technician"),
    ]
    users = []
    for env_key, default_username, role, display_name in credentials:
        username = os.environ.get(env_key, default_username).strip()
        password_key = f"{env_key.removesuffix('_USERNAME')}_PASSWORD"
        password = os.environ.get(password_key, "")
        if not username:
            raise CommandError(f"Set {env_key} to a nonempty username.")
        if not User.objects.filter(username=username).exists() and len(password) < 12:
            raise CommandError(
                f"Set {password_key} to a unique password of at least 12 characters."
            )
        users.append(ensure_demo_user(username, password, role, display_name))
    admin, staff, other_staff = users

    now = timezone.now()
    lead_specs = [
        {
            "name": "Alex Tan",
            "phone": "+65 8000 0001",
            "email": "alex.tan@example.test",
            "location": "Tampines · synthetic address",
            "service_type": Lead.Service.INSTALLATION,
            "requirements": "Two-room installation; synthetic demo request.",
            "source": Lead.Source.WEBSITE,
            "stage": Lead.Stage.NEW,
            "owner": None,
            "received_at": now - timedelta(hours=2),
        },
        {
            "name": "Mei Lin",
            "phone": "+65 8000 0002",
            "email": "mei.lin@example.test",
            "location": "Queenstown · synthetic address",
            "service_type": Lead.Service.MAINTENANCE,
            "requirements": "Routine servicing for a small office.",
            "source": Lead.Source.WHATSAPP,
            "stage": Lead.Stage.NEW,
            "owner": staff,
            "received_at": now - timedelta(days=1),
        },
        {
            "name": "Daniel Lim",
            "phone": "+65 8000 0003",
            "email": "daniel.lim@example.test",
            "location": "Bishan · synthetic address",
            "service_type": Lead.Service.REPAIR,
            "requirements": "Air conditioner inspection.",
            "source": Lead.Source.PHONE,
            "stage": Lead.Stage.CONTACTED,
            "first_contact_at": now - timedelta(days=4, hours=21),
            "owner": staff,
            "received_at": now - timedelta(days=5),
        },
        {
            "name": "Priya Nair",
            "phone": "+65 8000 0004",
            "email": "priya.nair@example.test",
            "location": "Serangoon · synthetic address",
            "service_type": Lead.Service.INSTALLATION,
            "requirements": "Three-room replacement quote.",
            "source": Lead.Source.REFERRAL,
            "stage": Lead.Stage.QUOTED,
            "first_contact_at": now - timedelta(days=39),
            "quote_amount": "1850.00",
            "owner": staff,
            "received_at": now - timedelta(days=40),
        },
        {
            "name": "Marcus Goh",
            "phone": "+65 8000 0005",
            "email": "marcus.goh@example.test",
            "location": "Jurong East · synthetic address",
            "service_type": Lead.Service.MAINTENANCE,
            "requirements": "Quarterly servicing package.",
            "source": Lead.Source.EMAIL,
            "stage": Lead.Stage.WON,
            "first_contact_at": now - timedelta(days=74),
            "quote_amount": "620.00",
            "closed_at": now - timedelta(days=10),
            "owner": admin,
            "received_at": now - timedelta(days=75),
        },
        {
            "name": "Sofia Ong",
            "phone": "+65 8000 0006",
            "email": "sofia.ong@example.test",
            "location": "Punggol · synthetic address",
            "service_type": Lead.Service.REPAIR,
            "requirements": "Synthetic customer chose another provider.",
            "source": Lead.Source.OTHER,
            "stage": Lead.Stage.LOST,
            "first_contact_at": now - timedelta(days=19),
            "closed_at": now - timedelta(days=5),
            "loss_reason": "Timing did not fit the customer's schedule.",
            "owner": other_staff,
            "received_at": now - timedelta(days=20),
        },
    ]
    with transaction.atomic():
        created_leads = []
        for spec in lead_specs:
            lead = Lead.objects.create(**spec, demo_seeded=True)
            created_leads.append(lead)
            ActivityEvent.objects.create(
                lead=lead,
                actor=spec.get("owner"),
                event_type="created",
                occurred_at=spec["received_at"],
                metadata={"source": spec["source"], "demo_seeded": True},
            )
            if spec["stage"] in {
                Lead.Stage.CONTACTED,
                Lead.Stage.QUOTED,
                Lead.Stage.WON,
                Lead.Stage.LOST,
            }:
                ActivityEvent.objects.create(
                    lead=lead,
                    actor=spec.get("owner"),
                    event_type="contact_recorded",
                    occurred_at=spec.get("first_contact_at", now),
                    metadata={"method": "phone", "summary": "Synthetic recorded follow-up."},
                )
            if spec["stage"] in {Lead.Stage.QUOTED, Lead.Stage.WON, Lead.Stage.LOST}:
                ActivityEvent.objects.create(
                    lead=lead,
                    actor=spec.get("owner"),
                    event_type="stage_changed",
                    occurred_at=spec.get("closed_at") or now,
                    metadata={
                        "stage_to": spec["stage"],
                        "quote_amount": str(spec.get("quote_amount", "")),
                    },
                )
            enqueue_inquiry_notification(lead)

        FollowUpTask.objects.create(
            lead=created_leads[1],
            created_by=staff,
            title="Call to confirm service date",
            due_at=now - timedelta(hours=3),
        )
        FollowUpTask.objects.create(
            lead=created_leads[0],
            created_by=staff,
            title="Call about installation options",
            due_at=now + timedelta(days=1),
        )
        FollowUpTask.objects.create(
            lead=created_leads[3],
            created_by=staff,
            title="Send quote reminder",
            due_at=now + timedelta(days=2),
        )
        pending = created_leads[3].email_executions.get()
        pending.status = EmailExecution.Status.FAILED
        pending.attempt_count = 1
        pending.first_attempt_at = now - timedelta(minutes=5)
        pending.next_attempt_at = now + timedelta(hours=20)
        pending.last_error_code = "timeout"
        pending.last_error_message = "The simulated provider timed out; safe retry is available."
        pending.save()
        EmailAttempt.objects.create(
            execution=pending,
            attempt_number=1,
            status=EmailAttempt.Status.UNCERTAIN,
            finished_at=now - timedelta(minutes=5),
            error_code="timeout",
            error_message="Simulated provider timeout.",
        )

    # Complete deterministic demo alerts immediately; leave the seeded failure available for retry.
    process_due(limit=100)
    return len(created_leads)


class Command(BaseCommand):
    help = "Create synthetic portfolio-demo accounts, leads, follow-ups, and fake email history."

    def handle(self, *args, **options):
        if not settings.DEMO_MODE:
            raise CommandError("Set DEMO_MODE=true before seeding demo records.")
        created = seed_demo_records()
        self.stdout.write(
            self.style.SUCCESS(f"Demo data ready; created {created} synthetic leads.")
        )
