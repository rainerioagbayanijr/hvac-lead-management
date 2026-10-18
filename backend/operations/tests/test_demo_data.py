import os
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from crm.models import Lead
from integrations.models import EmailExecution


@override_settings(DEMO_MODE=True)
class DemoDataCommandTests(TestCase):
    credentials = {
        "DEMO_ADMIN_PASSWORD": "Synthetic-Admin-Password-842!",
        "DEMO_STAFF_PASSWORD": "Synthetic-Staff-Password-842!",
        "DEMO_OTHER_STAFF_PASSWORD": "Synthetic-Other-Password-842!",
    }

    def test_seed_is_repeatable_and_contains_only_synthetic_records(self):
        with patch.dict(os.environ, self.credentials, clear=False):
            call_command("create_demo_data", verbosity=0)
            call_command("create_demo_data", verbosity=0)
        self.assertEqual(Lead.objects.count(), 6)
        self.assertTrue(Lead.objects.filter(demo_seeded=False).count() == 0)
        self.assertTrue(all(lead.email.endswith("@example.test") for lead in Lead.objects.all()))
        self.assertEqual(
            EmailExecution.objects.filter(status=EmailExecution.Status.FAILED).count(), 1
        )
        self.assertEqual(
            EmailExecution.objects.filter(status=EmailExecution.Status.DELIVERED).count(), 5
        )

    def test_reset_requires_flag_and_recreates_only_demo_records(self):
        with patch.dict(os.environ, self.credentials, clear=False):
            call_command("create_demo_data", verbosity=0)
            with self.assertRaises(CommandError):
                call_command("reset_demo_data", verbosity=0)
            self.assertEqual(Lead.objects.count(), 6)
            call_command("reset_demo_data", "--confirm-demo-reset", verbosity=0)
        self.assertEqual(Lead.objects.count(), 6)
        self.assertTrue(all(lead.demo_seeded for lead in Lead.objects.all()))
