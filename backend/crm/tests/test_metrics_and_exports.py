import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from crm.models import ActivityEvent, FollowUpTask, Lead

User = get_user_model()


class LeadArchiveAndExportTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("archive_admin", role=User.Role.ADMIN)
        self.staff = User.objects.create_user("archive_staff")
        self.lead = Lead.objects.create(
            name='=HYPERLINK("https://example.test")',
            email="synthetic@example.test",
            service_type=Lead.Service.REPAIR,
        )
        self.task = FollowUpTask.objects.create(
            lead=self.lead,
            created_by=self.admin,
            title="Synthetic follow-up",
            due_at=timezone.now() + timedelta(days=1),
        )
        self.client = APIClient()

    def action(self, suffix, actor, version=None):
        self.client.force_login(actor)
        return self.client.post(
            f"/api/v1/leads/{self.lead.pk}/{suffix}/",
            {
                "action_key": str(uuid.uuid4()),
                "expected_version": version or self.lead.version,
            },
            format="json",
        )

    def test_admin_can_archive_and_restore_with_append_only_history(self):
        archived = self.action("archive", self.admin)
        self.assertEqual(archived.status_code, 200)
        self.assertIsNotNone(archived.json()["archived_at"])
        self.assertEqual(archived.json()["version"], 2)
        self.assertEqual(ActivityEvent.objects.get().event_type, "lead_archived")
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, FollowUpTask.Status.CANCELLED)

        self.assertEqual(self.client.get("/api/v1/leads/").json()["count"], 0)
        self.assertEqual(self.client.get("/api/v1/leads/?archived=true").json()["count"], 1)
        self.assertEqual(self.client.get(f"/api/v1/leads/{self.lead.pk}/").status_code, 200)

        self.lead.refresh_from_db()
        restored = self.action("restore", self.admin, version=self.lead.version)
        self.assertEqual(restored.status_code, 200)
        self.assertIsNone(restored.json()["archived_at"])
        self.assertEqual(ActivityEvent.objects.count(), 2)

    def test_staff_cannot_archive_restore_or_view_archived_lead(self):
        self.assertEqual(self.action("archive", self.staff).status_code, 403)
        archived = self.action("archive", self.admin)
        self.assertEqual(archived.status_code, 200)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(f"/api/v1/leads/{self.lead.pk}/").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/leads/?archived=true").status_code, 400)

    def test_csv_export_is_admin_only_and_neutralizes_formula_cells(self):
        self.client.force_login(self.admin)
        response = self.client.get("/api/v1/leads/export.csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("'=HYPERLINK", response.content.decode())
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/api/v1/leads/export.csv").status_code, 403)
