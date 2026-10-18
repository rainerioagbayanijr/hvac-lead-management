from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings


class DevelopmentAccountTests(TestCase):
    @override_settings(DEBUG=False)
    def test_account_setup_is_disabled_in_production(self):
        with self.assertRaises(CommandError):
            call_command("create_dev_accounts")
        self.assertFalse(get_user_model().objects.exists())

    @override_settings(DEBUG=True)
    def test_account_setup_rejects_remote_database(self):
        with patch.dict(settings.DATABASES["default"], {"HOST": "db.example.test"}):
            with self.assertRaises(CommandError):
                call_command("create_dev_accounts")

    @override_settings(DEBUG=True)
    def test_local_setup_is_idempotent_and_never_prints_passwords(self):
        with TemporaryDirectory() as folder:
            with override_settings(BASE_DIR=Path(folder) / "backend"):
                output = StringIO()
                call_command("create_dev_accounts", stdout=output)
                notes = (Path(folder) / ".local-accounts.md").read_text(encoding="utf-8")
                for row in notes.splitlines():
                    if row.startswith("| demo_"):
                        username, _, password = [part.strip() for part in row.split("|")[1:4]]
                        self.assertTrue(
                            get_user_model().objects.get(username=username).check_password(password)
                        )
                        self.assertNotIn(password, output.getvalue())
                before = get_user_model().objects.get(username="demo_staff").password
                call_command("create_dev_accounts", stdout=output)
                self.assertEqual(get_user_model().objects.count(), 2)
                self.assertEqual(
                    before, get_user_model().objects.get(username="demo_staff").password
                )
