import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from crm.models import ActivityEvent, FollowUpTask, Lead

User = get_user_model()


class FollowUpTaskApiTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("task_staff")
        self.other_staff = User.objects.create_user("task_other")
        self.admin = User.objects.create_user("task_admin", role=User.Role.ADMIN)
        self.lead = Lead.objects.create(
            name="Synthetic task customer",
            email="task@example.test",
            service_type=Lead.Service.MAINTENANCE,
            owner=self.staff,
        )
        self.client = APIClient()
        self.client.force_login(self.staff)

    def post(self, path, **values):
        return self.client.post(
            path,
            {
                "action_key": str(uuid.uuid4()),
                "expected_version": self.lead.version,
                **values,
            },
            format="json",
        )

    @property
    def task_path(self):
        return f"/api/v1/leads/{self.lead.pk}/tasks/"

    def schedule(self, **overrides):
        values = {
            "title": "Call about installation dates",
            "details": "Offer weekday appointments.",
            "due_at": (timezone.now() + timedelta(days=1)).isoformat(),
        }
        values.update(overrides)
        return self.post(self.task_path, **values)

    def test_schedule_is_visible_in_lead_detail_and_activity(self):
        response = self.schedule()
        self.assertEqual(response.status_code, 200, response.content)
        task = response.json()["tasks"][0]
        self.assertEqual(task["title"], "Call about installation dates")
        self.assertEqual(task["status"], FollowUpTask.Status.PENDING)
        self.assertEqual(response.json()["activity"][-1]["event_type"], "task_scheduled")

    def test_schedule_retry_with_same_action_key_is_idempotent(self):
        action_key = str(uuid.uuid4())
        due_at = (timezone.now() + timedelta(days=1)).isoformat()
        body = {
            "action_key": action_key,
            "expected_version": 1,
            "title": "Call once",
            "due_at": due_at,
        }
        first = self.client.post(self.task_path, body, format="json")
        retry = self.client.post(self.task_path, body, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(FollowUpTask.objects.count(), 1)
        self.assertEqual(ActivityEvent.objects.filter(event_type="task_scheduled").count(), 1)

    def test_naive_schedule_time_is_rejected(self):
        response = self.schedule(due_at="2035-01-01T09:00:00")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(FollowUpTask.objects.count(), 0)

    def test_only_owner_or_admin_can_change_task(self):
        task = FollowUpTask.objects.create(
            lead=self.lead,
            created_by=self.staff,
            title="Owner-only task",
            due_at=timezone.now() + timedelta(days=1),
        )
        self.client.force_login(self.other_staff)
        response = self.post(
            f"/api/v1/leads/{self.lead.pk}/tasks/{task.pk}/complete/",
            expected_version=1,
        )
        self.assertEqual(response.status_code, 403)
        task.refresh_from_db()
        self.assertEqual(task.status, FollowUpTask.Status.PENDING)

    def test_reschedule_and_completion_record_state_and_history(self):
        task_id = self.schedule().json()["tasks"][0]["id"]
        new_due = (timezone.now() + timedelta(days=3)).isoformat()
        rescheduled = self.post(
            f"/api/v1/leads/{self.lead.pk}/tasks/{task_id}/reschedule/",
            expected_version=2,
            due_at=new_due,
        )
        self.assertEqual(rescheduled.status_code, 200, rescheduled.content)
        completed = self.post(
            f"/api/v1/leads/{self.lead.pk}/tasks/{task_id}/complete/",
            expected_version=3,
        )
        self.assertEqual(completed.status_code, 200, completed.content)
        task = FollowUpTask.objects.get(pk=task_id)
        self.assertEqual(task.status, FollowUpTask.Status.COMPLETED)
        self.assertIsNotNone(task.completed_at)
        self.assertEqual(
            list(self.lead.activity.values_list("event_type", flat=True)),
            ["task_scheduled", "task_rescheduled", "task_completed"],
        )

    def test_completion_retry_with_same_action_key_does_not_repeat_activity(self):
        task_id = self.schedule().json()["tasks"][0]["id"]
        action_key = str(uuid.uuid4())
        body = {"action_key": action_key, "expected_version": 2}
        path = f"/api/v1/leads/{self.lead.pk}/tasks/{task_id}/complete/"
        first = self.client.post(path, body, format="json")
        retry = self.client.post(path, body, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(ActivityEvent.objects.filter(event_type="task_completed").count(), 1)

    def test_task_responsibility_follows_admin_lead_reassignment(self):
        task = FollowUpTask.objects.create(
            lead=self.lead,
            created_by=self.staff,
            title="Reassigned follow-up",
            due_at=timezone.now() + timedelta(days=1),
        )
        self.client.force_login(self.admin)
        assignment = self.client.post(
            f"/api/v1/leads/{self.lead.pk}/assignment/",
            {
                "action_key": str(uuid.uuid4()),
                "expected_version": 1,
                "owner_id": self.other_staff.pk,
            },
            format="json",
        )
        self.assertEqual(assignment.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.lead.owner_id, self.other_staff.pk)
        self.assertEqual(
            self.client.get("/api/v1/tasks/?status=pending").json()["results"][0]["owner_name"],
            self.other_staff.display_name,
        )

    def test_lost_lead_cancels_pending_follow_ups_with_history(self):
        task_id = self.schedule().json()["tasks"][0]["id"]
        response = self.post(
            f"/api/v1/leads/{self.lead.pk}/stage/",
            expected_version=2,
            stage="lost",
            loss_reason="Customer postponed the work.",
        )
        self.assertEqual(response.status_code, 200, response.content)
        task = FollowUpTask.objects.get(pk=task_id)
        self.assertEqual(task.status, FollowUpTask.Status.CANCELLED)
        self.assertIsNotNone(task.cancelled_at)
        self.assertIn("1 open follow-up", response.json()["activity"][-1]["summary"])

    def test_won_lead_cancels_pending_follow_ups(self):
        self.lead.stage = Lead.Stage.QUOTED
        self.lead.quote_amount = Decimal("1200.00")
        self.lead.save(update_fields=["stage", "quote_amount"])
        task = FollowUpTask.objects.create(
            lead=self.lead,
            created_by=self.staff,
            title="Confirm installation",
            due_at=timezone.now() + timedelta(days=1),
        )
        response = self.post(
            f"/api/v1/leads/{self.lead.pk}/stage/",
            stage="won",
            loss_reason="",
        )
        self.assertEqual(response.status_code, 200, response.content)
        task.refresh_from_db()
        self.assertEqual(task.status, FollowUpTask.Status.CANCELLED)

    def test_closed_lead_cannot_receive_new_follow_up(self):
        self.lead.stage = Lead.Stage.LOST
        self.lead.loss_reason = "No longer needed"
        self.lead.closed_at = timezone.now()
        self.lead.save(update_fields=["stage", "loss_reason", "closed_at"])
        response = self.schedule()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(FollowUpTask.objects.count(), 0)

    def test_task_list_filters_overdue_and_requires_login(self):
        FollowUpTask.objects.create(
            lead=self.lead,
            created_by=self.staff,
            title="Overdue call",
            due_at=timezone.now() - timedelta(minutes=5),
        )
        count = self.client.get("/api/v1/tasks/?status=pending&due=overdue").json()["count"]
        self.assertEqual(count, 1)
        self.assertTrue(
            self.client.get("/api/v1/tasks/?status=pending&due=overdue").json()["results"][0][
                "is_overdue"
            ]
        )
        self.client.logout()
        self.assertEqual(self.client.get("/api/v1/tasks/").status_code, 403)
