from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView


class ProtectedProbe(APIView):
    """Test-only endpoint proving the global API defaults."""

    def get(self, request):
        return Response({"username": request.user.username})


urlpatterns = [path("protected/", ProtectedProbe.as_view())]


@override_settings(ROOT_URLCONF=__name__)
class PermissionFoundationTests(TestCase):
    def test_default_api_permission_rejects_anonymous_requests(self):
        response = self.client.get("/protected/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "not_authenticated")
        self.assertEqual(response.json()["request_id"], response["X-Request-ID"])

    def test_default_session_authentication_accepts_logged_in_user(self):
        user = get_user_model().objects.create_user("office")
        self.client.force_login(user)
        response = self.client.get("/protected/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"username": "office"})

    def test_inactive_user_session_is_not_authenticated(self):
        user = get_user_model().objects.create_user("inactive", is_active=False)
        self.client.force_login(user)
        response = self.client.get("/protected/")
        self.assertEqual(response.status_code, 403)

    def test_database_rejects_invalid_application_role(self):
        with transaction.atomic(), self.assertRaises(IntegrityError):
            get_user_model().objects.create_user("invalid-role", role="other")
