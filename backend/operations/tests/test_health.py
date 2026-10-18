import uuid
from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase


class HealthTests(TestCase):
    def test_public_readiness_checks_real_database(self):
        with self.assertNumQueries(1):
            response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response["Cache-Control"], "no-store")
        uuid.UUID(response["X-Request-ID"])

    def test_hosting_health_alias_works(self):
        self.assertEqual(self.client.get("/health/").json(), {"status": "ok"})

    def test_database_failure_is_503_without_private_details(self):
        with patch(
            "operations.health.connection.cursor", side_effect=OperationalError("private-db-detail")
        ):
            response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotContains(response, "private-db-detail", status_code=503)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_readiness_rejects_mutating_requests(self):
        response = self.client.post("/api/v1/health/")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()["code"], "method_not_allowed")

    def test_request_references_do_not_trust_client_input(self):
        first = self.client.get("/api/v1/health/", HTTP_X_REQUEST_ID="untrusted-input")
        second = self.client.get("/api/v1/health/")
        self.assertNotEqual(first["X-Request-ID"], "untrusted-input")
        self.assertNotEqual(first["X-Request-ID"], second["X-Request-ID"])
