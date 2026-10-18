from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from crm.models import ActivityEvent, FollowUpTask, Lead

User = get_user_model()


class DashboardAndLeadQueryTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("dashboard_admin", role=User.Role.ADMIN)
        self.staff = User.objects.create_user("dashboard_staff")
        self.client = APIClient()
        self.client.force_login(self.staff)

    def create_lead(self, **values):
        defaults = {
            "name": "Synthetic HVAC customer",
            "phone": "+65 8000 0000",
            "service_type": Lead.Service.MAINTENANCE,
            "source": Lead.Source.PHONE,
            "received_at": timezone.now() - timedelta(days=10),
        }
        defaults.update(values)
        return Lead.objects.create(**defaults)

    def test_search_and_filters_are_combined_and_stable(self):
        match = self.create_lead(name="Alice Example", owner=self.staff)
        self.create_lead(name="Bob Example", source=Lead.Source.EMAIL)
        response = self.client.get(
            "/api/v1/leads/", {"q": "alice", "source": "phone", "owner": "mine"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["id"], str(match.pk))

    def test_invalid_filter_and_admin_only_owner_filter_are_rejected(self):
        self.assertEqual(self.client.get("/api/v1/leads/?stage=unknown").status_code, 400)
        self.assertEqual(self.client.get("/api/v1/leads/?owner=2").status_code, 400)

    def test_overdue_filter_requires_pending_task_and_matches_only_its_lead(self):
        overdue = self.create_lead(name="Overdue customer")
        current = timezone.now()
        FollowUpTask.objects.create(
            lead=overdue,
            created_by=self.staff,
            title="Call customer",
            due_at=current - timedelta(minutes=1),
        )
        upcoming = self.create_lead(name="Upcoming customer")
        FollowUpTask.objects.create(
            lead=upcoming,
            created_by=self.staff,
            title="Call customer",
            due_at=current + timedelta(days=1),
        )
        response = self.client.get("/api/v1/leads/?due=overdue")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["id"], str(overdue.pk))

    def test_dashboard_metrics_use_receipt_and_first_contact_timestamps(self):
        now = timezone.now()
        self.create_lead(
            received_at=now - timedelta(days=5),
            first_contact_at=now - timedelta(days=4, hours=23),
        )
        self.create_lead(
            stage=Lead.Stage.QUOTED,
            quote_amount=Decimal("250.00"),
            received_at=now - timedelta(days=60),
            first_contact_at=now - timedelta(days=59),
        )
        winner = self.create_lead(
            name="Won customer",
            stage=Lead.Stage.WON,
            quote_amount=Decimal("500.00"),
            closed_at=now,
            received_at=now - timedelta(days=60),
        )
        self.assertFalse(ActivityEvent.objects.filter(lead=winner).exists())

        response = self.client.get("/api/v1/dashboard/")
        self.assertEqual(response.status_code, 200)
        metrics = response.json()
        self.assertEqual(metrics["pipeline"][Lead.Stage.QUOTED], 1)
        self.assertEqual(metrics["pipeline"][Lead.Stage.WON], 1)
        self.assertEqual(metrics["new_leads_30d"], 1)
        self.assertEqual(metrics["response_time_30d"]["eligible_count"], 1)
        self.assertEqual(metrics["response_time_30d"]["responded_count"], 1)
        self.assertEqual(metrics["response_time_30d"]["median_seconds"], 3600)
        self.assertEqual(metrics["open_quoted_value_sgd"], "250.00")
        self.assertEqual(metrics["mature_cohort_win_rate_90d"]["won_count"], 1)
        self.assertEqual(metrics["mature_cohort_win_rate_90d"]["eligible_count"], 2)

    def test_dashboard_is_authenticated(self):
        self.client.logout()
        self.assertEqual(self.client.get("/api/v1/dashboard/").status_code, 403)
