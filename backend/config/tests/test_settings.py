import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase


class ProductionSettingsTests(SimpleTestCase):
    """Use isolated processes so production imports cannot alter running test settings."""

    def load_settings(self, **overrides):
        environment = os.environ.copy()
        environment.update(
            DJANGO_SETTINGS_MODULE="config.settings.production",
            DJANGO_SECRET_KEY="synthetic-settings-test-key-" * 3,
            DJANGO_ALLOWED_HOSTS="crm.example.test",
            POSTGRES_DB="settings_test",
            POSTGRES_USER="settings_test",
            POSTGRES_PASSWORD="synthetic-settings-test-password",
            POSTGRES_SSLMODE="require",
            DJANGO_TRUST_PROXY="false",
        )
        environment.update(overrides)
        return subprocess.run(
            [
                sys.executable,
                "-c",
                "from django.conf import settings; "
                "print(settings.DEBUG, settings.SESSION_COOKIE_SECURE, "
                "settings.CSRF_COOKIE_SECURE)",
            ],
            cwd=Path(__file__).resolve().parents[2],
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def test_production_disables_debug_and_secures_cookies(self):
        result = self.load_settings()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False True True")

    def test_production_rejects_missing_secret(self):
        result = self.load_settings(DJANGO_SECRET_KEY="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set DJANGO_SECRET_KEY", result.stderr)

    def test_production_rejects_wildcard_host(self):
        result = self.load_settings(DJANGO_ALLOWED_HOSTS="*")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("explicit DJANGO_ALLOWED_HOSTS", result.stderr)

    def test_production_rejects_unencrypted_database_configuration(self):
        result = self.load_settings(POSTGRES_SSLMODE="disable")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("secure POSTGRES_SSLMODE", result.stderr)
