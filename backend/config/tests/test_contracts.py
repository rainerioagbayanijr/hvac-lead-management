from django.test import SimpleTestCase, override_settings
from django.urls import path
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView


class ValidationProbe(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        raise ValidationError({"email": ["Enter a valid email address."]})


class UnexpectedErrorProbe(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        raise RuntimeError("private implementation detail")


urlpatterns = [
    path("validation/", ValidationProbe.as_view()),
    path("unexpected/", UnexpectedErrorProbe.as_view()),
]


@override_settings(ROOT_URLCONF=__name__)
class ErrorContractTests(SimpleTestCase):
    def test_validation_errors_preserve_field_messages_and_request_reference(self):
        response = self.client.get("/validation/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "validation_error")
        self.assertEqual(response.json()["fields"], {"email": ["Enter a valid email address."]})
        self.assertEqual(response.json()["request_id"], response["X-Request-ID"])

    def test_unexpected_errors_are_generic_json_without_exception_details(self):
        response = self.client.get("/unexpected/")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["code"], "internal_error")
        self.assertNotContains(response, "private implementation detail", status_code=500)
        self.assertEqual(response.json()["request_id"], response["X-Request-ID"])
