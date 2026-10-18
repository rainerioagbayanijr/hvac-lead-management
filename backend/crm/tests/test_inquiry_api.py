import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from crm.models import ActivityEvent, Lead


def inquiry_payload(**overrides):
    values = {
        "submission_key": str(uuid.uuid4()),
        "name": "Synthetic Customer",
        "email": "customer@example.test",
        "service_type": "maintenance",
        "privacy_acknowledged": True,
    }
    values.update(overrides)
    return values


class InquiryApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def post(self, values):
        return self.client.post("/api/v1/inquiries/", values, format="json")

    def test_public_inquiry_creates_one_new_unassigned_lead_and_event(self):
        response = self.post(inquiry_payload(email=" Person@EXAMPLE.test "))
        self.assertEqual(response.status_code, 201)
        lead = Lead.objects.get()
        self.assertEqual(response.json(), {"reference": str(lead.pk)})
        self.assertEqual((lead.stage, lead.source, lead.owner), ("new", "website", None))
        self.assertEqual(lead.email, "person@example.test")
        self.assertEqual(lead.activity.count(), 1)
        self.assertEqual(lead.activity.get().metadata["privacy_notice_version"], "1")

    def test_replay_returns_original_reference_with_no_extra_event(self):
        values = inquiry_payload()
        first = self.post(values)
        replay = self.post(values)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(first.json(), replay.json())
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(ActivityEvent.objects.count(), 1)

    def test_different_payload_under_same_key_is_conflict(self):
        values = inquiry_payload()
        self.post(values)
        response = self.post({**values, "name": "A different customer"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "submission_conflict")
        self.assertEqual(Lead.objects.get().name, "Synthetic Customer")

    def test_replay_uses_original_fingerprint_after_staff_edit(self):
        values = inquiry_payload()
        self.post(values)
        lead = Lead.objects.get()
        lead.name = "Corrected synthetic name"
        lead.save()
        response = self.post(values)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Lead.objects.get().name, "Corrected synthetic name")

    def test_phone_only_inquiry_normalizes_digits(self):
        response = self.post(inquiry_payload(email="", phone="+65 8000 0000"))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Lead.objects.get().normalized_phone, "6580000000")

    def test_invalid_fields_return_field_errors_without_storing_leads(self):
        for changes in [
            {"email": "", "phone": ""},
            {"name": " "},
            {"email": "invalid"},
            {"service_type": "invalid"},
            {"submission_key": "invalid"},
            {"privacy_acknowledged": False},
            {"phone": "no digits"},
            {"requirements": "x" * 4001},
        ]:
            with self.subTest(changes=changes):
                response = self.post(inquiry_payload(**changes))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["code"], "validation_error")
        self.assertEqual(Lead.objects.count(), 0)

    def test_public_client_cannot_choose_privileged_fields(self):
        for field, value in [
            ("stage", "won"),
            ("owner", 1),
            ("source", "phone"),
            ("role", "admin"),
        ]:
            with self.subTest(field=field):
                self.assertEqual(self.post(inquiry_payload(**{field: value})).status_code, 400)
        self.assertFalse(Lead.objects.exists())

    def test_honeypot_is_rejected(self):
        self.assertEqual(
            self.post(inquiry_payload(company_website="https://bot.example.test")).status_code, 400
        )
        self.assertFalse(Lead.objects.exists())

    def test_event_failure_rolls_back_lead(self):
        with patch(
            "crm.services.ActivityEvent.objects.create",
            side_effect=RuntimeError("synthetic-failure"),
        ):
            response = self.post(inquiry_payload())
        self.assertEqual(response.status_code, 500)
        self.assertFalse(Lead.objects.exists())
        self.assertNotContains(response, "synthetic-failure", status_code=500)

    def test_same_contact_with_different_keys_is_allowed(self):
        self.assertEqual(self.post(inquiry_payload()).status_code, 201)
        self.assertEqual(self.post(inquiry_payload()).status_code, 201)
        self.assertEqual(Lead.objects.count(), 2)

    @override_settings(PUBLIC_INQUIRIES_PER_HOUR=1)
    def test_rate_limit_returns_retry_after(self):
        self.post(inquiry_payload())
        response = self.post(inquiry_payload())
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)
        self.assertEqual(Lead.objects.count(), 1)

    def test_intake_always_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        self.assertEqual(
            client.post("/api/v1/inquiries/", inquiry_payload(), format="json").status_code, 403
        )
        token = client.get("/api/v1/auth/csrf/").json()["csrf_token"]
        response = client.post(
            "/api/v1/inquiries/", inquiry_payload(), format="json", HTTP_X_CSRFTOKEN=token
        )
        self.assertEqual(response.status_code, 201)

    def test_oversized_and_malformed_bodies_are_rejected(self):
        response = self.client.post("/api/v1/inquiries/", {"body": "x" * 70000}, format="json")
        self.assertEqual(response.status_code, 413)
        response = self.client.post(
            "/api/v1/inquiries/", '{"invalid":', content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Lead.objects.exists())


class LeadReadApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("office")
        self.other = get_user_model().objects.create_user("other")
        self.lead = Lead.objects.create(
            name="Synthetic", email="customer@example.test", service_type="repair", owner=self.other
        )
        self.client = APIClient()

    def test_anonymous_cannot_read_list_or_known_detail(self):
        for path in ["/api/v1/leads/", f"/api/v1/leads/{self.lead.pk}/"]:
            self.assertEqual(self.client.get(path).status_code, 403)

    def test_staff_can_read_other_owners_lead_without_private_submission_fields(self):
        self.client.force_login(self.user)
        response = self.client.get(f"/api/v1/leads/{self.lead.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["owner_name"], "other")
        for field in ["request_fingerprint", "submission_key", "normalized_phone"]:
            self.assertNotIn(field, response.json())

    def test_list_is_paginated(self):
        Lead.objects.bulk_create(
            [
                Lead(
                    name=f"Synthetic {number}", email="customer@example.test", service_type="repair"
                )
                for number in range(26)
            ]
        )
        self.client.force_login(self.user)
        response = self.client.get("/api/v1/leads/")
        self.assertEqual(response.json()["count"], 27)
        self.assertEqual(len(response.json()["results"]), 25)
        self.assertIsNotNone(response.json()["next"])
        self.assertEqual(len(self.client.get("/api/v1/leads/?page=2").json()["results"]), 2)

    def test_only_the_manual_create_endpoint_accepts_writes(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post("/api/v1/leads/", {}, format="json").status_code, 400)
        for method in [self.client.patch, self.client.delete]:
            self.assertEqual(
                method(f"/api/v1/leads/{self.lead.pk}/", {}, format="json").status_code, 405
            )

    def test_missing_lead_is_safe_404(self):
        self.client.force_login(self.user)
        response = self.client.get(f"/api/v1/leads/{uuid.uuid4()}/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "not_found")
