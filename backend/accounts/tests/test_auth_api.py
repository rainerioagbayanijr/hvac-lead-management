from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


class SessionApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("office", password="Synthetic-password-42")
        self.client = APIClient(enforce_csrf_checks=True)

    def post(self, path, values=None):
        token = self.client.get("/api/v1/auth/csrf/").json()["csrf_token"]
        return self.client.post(path, values or {}, format="json", HTTP_X_CSRFTOKEN=token)

    def login(self):
        return self.post(
            "/api/v1/auth/login/", {"username": "office", "password": "Synthetic-password-42"}
        )

    def test_anonymous_session_is_public_and_not_cacheable(self):
        response = self.client.get("/api/v1/auth/session/")
        self.assertEqual(response.json(), {"authenticated": False})
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_login_requires_csrf_even_when_anonymous(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "office", "password": "Synthetic-password-42"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "csrf_failed")

    def test_login_sets_session_and_returns_safe_user_fields(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["authenticated"])
        self.assertEqual(response.json()["user"]["role"], "staff")
        self.assertNotIn("password", response.json()["user"])
        self.assertTrue(self.client.cookies[settings.SESSION_COOKIE_NAME]["httponly"])
        self.assertEqual(self.client.get("/api/v1/leads/").status_code, 200)

    def test_login_rotates_existing_session_and_csrf_secret(self):
        session = self.client.session
        session["synthetic"] = True
        session.save()
        before = session.session_key
        self.client.get("/api/v1/auth/csrf/")
        old_csrf = self.client.cookies["csrftoken"].value
        self.login()
        self.assertNotEqual(before, self.client.session.session_key)
        self.assertNotEqual(old_csrf, self.client.cookies["csrftoken"].value)
        self.assertLessEqual(self.client.session.get_expiry_age(), 8 * 60 * 60)

    def test_invalid_and_inactive_credentials_are_generic(self):
        wrong = self.post("/api/v1/auth/login/", {"username": "office", "password": "incorrect"})
        self.user.is_active = False
        self.user.save()
        inactive = self.login()
        self.assertEqual(wrong.status_code, 403)
        self.assertEqual(wrong.json()["code"], "invalid_credentials")
        self.assertEqual(wrong.json()["message"], inactive.json()["message"])

    def test_logout_requires_csrf_and_destroys_session(self):
        self.login()
        key = self.client.session.session_key
        rejected = self.client.post("/api/v1/auth/logout/", {}, format="json")
        self.assertEqual(rejected.status_code, 403)
        self.assertTrue(self.client.get("/api/v1/auth/session/").json()["authenticated"])
        response = self.post("/api/v1/auth/logout/")
        self.assertEqual(response.json(), {"authenticated": False})
        self.assertFalse(Session.objects.filter(session_key=key).exists())
        self.assertEqual(self.client.get("/api/v1/leads/").status_code, 403)

    def test_inactive_account_loses_existing_session_access(self):
        self.login()
        self.user.is_active = False
        self.user.save()
        self.assertFalse(self.client.get("/api/v1/auth/session/").json()["authenticated"])

    def test_untrusted_origin_is_rejected(self):
        token = self.client.get("/api/v1/auth/csrf/").json()["csrf_token"]
        response = self.client.post(
            "/api/v1/auth/login/",
            {},
            format="json",
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN="https://untrusted.example.test",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "csrf_failed")

    @override_settings(LOGIN_ATTEMPTS_PER_ACCOUNT=1)
    def test_login_account_limit_has_retry_after(self):
        self.login()
        response = self.login()
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)

    @override_settings(LOGIN_ATTEMPTS_PER_IP=1)
    def test_login_ip_limit_applies_across_usernames(self):
        self.post("/api/v1/auth/login/", {"username": "unknown-a", "password": "incorrect"})
        response = self.post(
            "/api/v1/auth/login/", {"username": "unknown-b", "password": "incorrect"}
        )
        self.assertEqual(response.status_code, 429)
