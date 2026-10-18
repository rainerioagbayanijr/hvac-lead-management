import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from crm.models import Lead


class LeadFoundationTests(TestCase):
    """Model and PostgreSQL constraints, not the milestone-2 submission API."""

    def make_lead(self, **overrides):
        fields = {
            "name": "Synthetic Customer",
            "email": "customer@example.test",
            "service_type": "maintenance",
        }
        fields.update(overrides)
        return Lead.objects.create(**fields)

    def test_new_lead_defaults_and_aware_timestamps(self):
        lead = self.make_lead()
        self.assertEqual(lead.stage, "new")
        self.assertIsNone(lead.owner)
        self.assertEqual(lead.version, 1)
        self.assertTrue(timezone.is_aware(lead.received_at))
        self.assertTrue(timezone.is_aware(lead.created_at))

    def test_validation_normalizes_contact_details(self):
        lead = Lead(
            name="  Synthetic Customer  ",
            email=" Person@EXAMPLE.test ",
            phone=" +65 8000 0000 ",
            service_type="repair",
        )
        lead.full_clean()
        self.assertEqual(lead.name, "Synthetic Customer")
        self.assertEqual(lead.email, "person@example.test")
        self.assertEqual(lead.normalized_phone, "6580000000")

    def test_database_requires_contact_method_even_without_python_validation(self):
        with transaction.atomic(), self.assertRaises(IntegrityError):
            self.make_lead(email="", phone="")

    def test_database_rejects_whitespace_contact(self):
        with transaction.atomic(), self.assertRaises(IntegrityError):
            self.make_lead(email=" ", phone=" ")

    def test_database_rejects_blank_name(self):
        with transaction.atomic(), self.assertRaises(IntegrityError):
            self.make_lead(name=" ")

    def test_database_rejects_unknown_choices(self):
        for field in ["stage", "source", "service_type"]:
            with self.subTest(field=field), transaction.atomic(), self.assertRaises(IntegrityError):
                self.make_lead(**{field: "invalid"})

    def test_database_rejects_zero_version(self):
        with transaction.atomic(), self.assertRaises(IntegrityError):
            self.make_lead(version=0)

    def test_submission_key_is_unique(self):
        key = uuid.uuid4()
        self.make_lead(submission_key=key, request_fingerprint="a" * 64)
        with transaction.atomic(), self.assertRaises(IntegrityError):
            self.make_lead(submission_key=key, request_fingerprint="a" * 64)

    def test_submission_key_requires_a_valid_fingerprint(self):
        for fingerprint in ["", "invalid", "G" * 64]:
            with (
                self.subTest(fingerprint=fingerprint),
                transaction.atomic(),
                self.assertRaises(IntegrityError),
            ):
                self.make_lead(submission_key=uuid.uuid4(), request_fingerprint=fingerprint)

    def test_manual_leads_can_share_contact_details(self):
        self.make_lead()
        self.make_lead()
        self.assertEqual(Lead.objects.count(), 2)

    def test_submission_identity_survives_ordinary_edits(self):
        lead = self.make_lead(submission_key=uuid.uuid4(), request_fingerprint="a" * 64)
        lead.name = "Updated synthetic name"
        lead.save(update_fields=["name", "updated_at"])
        lead.refresh_from_db()
        self.assertEqual(lead.request_fingerprint, "a" * 64)

    def test_model_save_rejects_submission_identity_changes(self):
        for field, value in [("submission_key", uuid.uuid4()), ("request_fingerprint", "b" * 64)]:
            with self.subTest(field=field):
                lead = self.make_lead(submission_key=uuid.uuid4(), request_fingerprint="a" * 64)
                setattr(lead, field, value)
                with self.assertRaisesMessage(ValidationError, "cannot be changed"):
                    lead.save()

    def test_validation_rejects_future_receipt_time(self):
        lead = Lead(
            name="Synthetic",
            email="customer@example.test",
            service_type="repair",
            received_at=timezone.now() + timedelta(days=1),
        )
        with self.assertRaises(ValidationError) as caught:
            lead.full_clean()
        self.assertIn("received_at", caught.exception.message_dict)

    def test_validation_rejects_naive_receipt_time(self):
        lead = Lead(
            name="Synthetic",
            email="customer@example.test",
            service_type="repair",
            received_at=timezone.now().replace(tzinfo=None),
        )
        with self.assertRaises(ValidationError) as caught:
            lead.full_clean()
        self.assertIn("received_at", caught.exception.message_dict)

    def test_validation_rejects_phone_without_digits(self):
        lead = Lead(name="Synthetic", phone="not a phone", service_type="repair")
        with self.assertRaises(ValidationError) as caught:
            lead.full_clean()
        self.assertIn("phone", caught.exception.message_dict)

    def test_validation_reports_missing_required_fields_without_crashing(self):
        for field in ["name", "received_at"]:
            with self.subTest(field=field):
                lead = Lead(name="Synthetic", email="customer@example.test", service_type="repair")
                setattr(lead, field, None)
                with self.assertRaises(ValidationError) as caught:
                    lead.full_clean()
                self.assertIn(field, caught.exception.message_dict)

    def test_assigned_user_is_protected_from_deletion(self):
        user = get_user_model().objects.create_user("office")
        self.make_lead(owner=user)
        with self.assertRaises(ProtectedError):
            user.delete()
