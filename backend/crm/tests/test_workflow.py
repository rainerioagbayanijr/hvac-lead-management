import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from config.api import Conflict
from crm.models import ActivityEvent, Lead
from crm.workflow import claim_lead

User = get_user_model()


def lead_payload(**overrides):
    payload = {
        "name": "Synthetic workflow customer",
        "phone": "+65 8000 0000",
        "email": "",
        "location": "Synthetic site",
        "service_type": "maintenance",
        "requirements": "Synthetic test request",
        "source": "phone",
    }
    payload.update(overrides)
    return payload


class LeadWorkflowApiTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("workflow_staff")
        self.other_staff = User.objects.create_user("other_staff")
        self.admin = User.objects.create_user("workflow_admin", role=User.Role.ADMIN)
        self.lead = Lead.objects.create(
            name="Synthetic customer", email="customer@example.test", service_type="repair"
        )
        self.client = APIClient()

    def action(self, path, version=None, **values):
        return self.client.post(
            path,
            {
                "action_key": str(uuid.uuid4()),
                "expected_version": version if version is not None else self.lead.version,
                **values,
            },
            format="json",
        )

    def login(self, user):
        self.client.force_login(user)

    def path(self, action):
        return f"/api/v1/leads/{self.lead.pk}/{action}/"

    def test_staff_sees_all_leads_but_cannot_change_another_staff_member_lead(self):
        self.lead.owner = self.other_staff
        self.lead.save(update_fields=["owner"])
        self.login(self.staff)
        self.assertEqual(self.client.get("/api/v1/leads/").status_code, 200)
        response = self.action(self.path("notes"), body="Should not be saved")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.lead.activity.count(), 0)

    def test_staff_can_claim_an_unassigned_lead_only_once(self):
        self.login(self.staff)
        response = self.action(self.path("claim"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["owner_id"], self.staff.pk)
        self.assertEqual(response.json()["version"], 2)
        self.client.force_login(self.other_staff)
        second = self.action(self.path("claim"), version=2)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(Lead.objects.get(pk=self.lead.pk).owner_id, self.staff.pk)

    def test_stale_version_is_rejected_without_creating_history(self):
        self.lead.owner = self.staff
        self.lead.save(update_fields=["owner"])
        self.login(self.staff)
        self.assertEqual(self.action(self.path("notes"), body="First note").status_code, 200)
        stale = self.action(self.path("notes"), version=1, body="Stale note")
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.lead.activity.count(), 1)

    def test_note_retry_is_idempotent_and_key_reuse_with_changed_body_conflicts(self):
        self.lead.owner = self.staff
        self.lead.save(update_fields=["owner"])
        self.login(self.staff)
        key = str(uuid.uuid4())
        payload = {"action_key": key, "expected_version": 1, "body": "Called about service dates."}
        first = self.client.post(self.path("notes"), payload, format="json")
        retry = self.client.post(self.path("notes"), payload, format="json")
        changed = self.client.post(
            self.path("notes"), {**payload, "body": "Changed note."}, format="json"
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json()["version"], 2)
        self.assertEqual(changed.status_code, 409)
        self.assertEqual(self.lead.activity.count(), 1)
        self.assertEqual(self.lead.activity.get().metadata["body"], "Called about service dates.")

    def test_contact_records_first_response_once_and_advances_new_to_contacted(self):
        self.lead.owner = self.staff
        self.lead.save(update_fields=["owner"])
        self.login(self.staff)
        first = self.action(self.path("contact"), method="phone", summary="Asked for availability.")
        contacted_at = first.json()["first_contact_at"]
        self.assertEqual(first.json()["stage"], Lead.Stage.CONTACTED)
        self.assertIsNotNone(contacted_at)
        second = self.action(
            self.path("contact"), version=2, method="email", summary="Sent service details."
        )
        self.assertEqual(second.json()["first_contact_at"], contacted_at)
        self.assertEqual(ActivityEvent.objects.filter(event_type="contact_recorded").count(), 2)

    def test_quote_won_and_lost_requirements_are_enforced(self):
        self.lead.owner = self.staff
        self.lead.save(update_fields=["owner"])
        self.login(self.staff)
        missing_quote = self.action(self.path("stage"), stage="quoted")
        self.assertEqual(missing_quote.status_code, 400)
        self.assertEqual(self.lead.version, 1)
        self.assertEqual(self.action(self.path("contact"), method="phone").status_code, 200)
        quoted = self.action(self.path("stage"), version=2, stage="quoted", quote_amount="2450.00")
        self.assertEqual(quoted.status_code, 200)
        self.assertEqual(quoted.json()["quote_amount"], "2450.00")
        won = self.action(self.path("stage"), version=3, stage="won")
        self.assertEqual(won.status_code, 200)
        self.assertIsNotNone(won.json()["closed_at"])
        self.assertEqual(won.json()["stage"], Lead.Stage.WON)
        self.assertEqual(ActivityEvent.objects.filter(event_type="stage_changed").count(), 2)

    def test_lost_can_happen_from_new_and_admin_reopen_preserves_closure_history(self):
        self.lead.owner = self.staff
        self.lead.save(update_fields=["owner"])
        self.login(self.staff)
        lost = self.action(self.path("stage"), stage="lost", loss_reason="Customer postponed work.")
        self.assertEqual(lost.status_code, 200)
        self.assertEqual(lost.json()["loss_reason"], "Customer postponed work.")
        self.client.force_login(self.admin)
        reopened = self.action(self.path("reopen"), version=2, stage="new")
        self.assertEqual(reopened.status_code, 200)
        self.assertIsNone(reopened.json()["closed_at"])
        self.assertEqual(reopened.json()["loss_reason"], "")
        events = list(self.lead.activity.values_list("event_type", "metadata"))
        self.assertEqual([event[0] for event in events], ["stage_changed", "lead_reopened"])
        self.assertIn("Customer postponed work.", events[0][1]["loss_reason"])

    def test_admin_assigns_reassigns_and_unassigns_leads(self):
        self.login(self.admin)
        team = self.client.get("/api/v1/team/")
        self.assertEqual(team.status_code, 200)
        assigned = self.action(self.path("assignment"), owner_id=self.staff.pk)
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(assigned.json()["owner_id"], self.staff.pk)
        reassigned = self.action(self.path("assignment"), version=2, owner_id=self.other_staff.pk)
        self.assertEqual(reassigned.json()["owner_id"], self.other_staff.pk)
        unassigned = self.action(self.path("assignment"), version=3, owner_id=None)
        self.assertIsNone(unassigned.json()["owner_id"])

    def test_staff_cannot_use_admin_assignment_reopen_or_team_options(self):
        self.login(self.staff)
        self.assertEqual(self.client.get("/api/v1/team/").status_code, 403)
        self.assertEqual(
            self.action(self.path("assignment"), owner_id=self.staff.pk).status_code, 403
        )
        self.assertEqual(self.action(self.path("claim")).status_code, 200)
        lost = self.action(self.path("stage"), version=2, stage="lost", loss_reason="No response.")
        self.assertEqual(lost.status_code, 200)
        self.assertEqual(self.action(self.path("reopen"), version=2, stage="new").status_code, 403)

    def test_session_workflow_writes_require_csrf(self):
        self.lead.owner = self.staff
        self.lead.save(update_fields=["owner"])
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.staff)
        payload = {
            "action_key": str(uuid.uuid4()),
            "expected_version": 1,
            "body": "A protected workflow note.",
        }
        denied = client.post(self.path("notes"), payload, format="json")
        self.assertEqual(denied.status_code, 403)
        token = client.get("/api/v1/auth/csrf/").json()["csrf_token"]
        allowed = client.post(self.path("notes"), payload, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(allowed.status_code, 200)

    def test_invalid_fields_and_methods_are_rejected(self):
        self.lead.owner = self.staff
        self.lead.save(update_fields=["owner"])
        self.login(self.staff)
        invalid = self.action(self.path("contact"), method="carrier pigeon")
        self.assertEqual(invalid.status_code, 400)
        privileged = self.action(self.path("contact"), method="phone", stage="won")
        self.assertEqual(privileged.status_code, 400)
        self.assertEqual(self.client.delete(f"/api/v1/leads/{self.lead.pk}/").status_code, 405)

    def test_event_failure_rolls_back_lead_change(self):
        self.lead.owner = self.staff
        self.lead.save(update_fields=["owner"])
        self.login(self.staff)
        with patch("crm.workflow.ActivityEvent.objects.create", side_effect=RuntimeError("fail")):
            response = self.action(self.path("notes"), body="This must roll back")
        self.assertEqual(response.status_code, 500)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.version, 1)
        self.assertFalse(self.lead.activity.exists())

    def test_manual_entry_tracks_source_time_and_staff_owner(self):
        self.login(self.staff)
        received = (timezone.now() - timedelta(days=2)).isoformat()
        response = self.client.post(
            "/api/v1/leads/", lead_payload(received_at=received), format="json"
        )
        self.assertEqual(response.status_code, 201)
        manual = Lead.objects.get(name="Synthetic workflow customer")
        self.assertEqual(manual.owner_id, self.staff.pk)
        self.assertEqual(manual.created_by_id, self.staff.pk)
        self.assertEqual(manual.source, "phone")
        self.assertEqual(manual.received_at.isoformat(), received)
        self.assertEqual(manual.activity.get().event_type, "manual_created")

    def test_manual_entry_rejects_future_naive_and_missing_contact(self):
        self.login(self.staff)
        values = lead_payload()
        for change in [
            {"received_at": timezone.now().isoformat().replace("+00:00", "")},
            {"received_at": (timezone.now() + timedelta(days=1)).isoformat()},
            {"phone": "", "email": ""},
        ]:
            with self.subTest(change=change):
                response = self.client.post("/api/v1/leads/", {**values, **change}, format="json")
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Lead.objects.count(), 1)


class ConcurrentLeadClaimTests(TransactionTestCase):
    def test_two_staff_members_racing_to_claim_have_one_winner(self):
        lead = Lead.objects.create(
            name="Synthetic claim race", email="race@example.test", service_type="repair"
        )
        staff = [User.objects.create_user("claim_a"), User.objects.create_user("claim_b")]
        barrier = Barrier(2)

        def claim(user):
            connections.close_all()
            try:
                barrier.wait(timeout=5)
                return claim_lead(lead.pk, user, uuid.uuid4(), 1).owner_id
            except Conflict:
                return None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, staff))
        self.assertEqual(sum(value is not None for value in results), 1)
        lead.refresh_from_db()
        self.assertIn(lead.owner_id, [user.pk for user in staff])
        self.assertEqual(lead.activity.filter(event_type="claimed").count(), 1)
