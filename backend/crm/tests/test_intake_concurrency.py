from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import connections
from django.test import TransactionTestCase

from config.api import Conflict
from crm.api.serializers import InquirySerializer
from crm.models import ActivityEvent, Lead
from crm.services import create_inquiry
from crm.tests.test_inquiry_api import inquiry_payload


class ConcurrentIntakeTests(TransactionTestCase):
    def race(self, payloads):
        barrier = Barrier(2)
        original_clean = Lead.full_clean

        def validated_together(lead, *args, **kwargs):
            original_clean(lead, *args, **kwargs)
            barrier.wait(timeout=5)

        def submit(payload):
            connections.close_all()
            try:
                serializer = InquirySerializer(data=payload)
                serializer.is_valid(raise_exception=True)
                lead, created = create_inquiry(serializer.validated_data)
                return str(lead.pk), created
            except Conflict:
                return "conflict", False
            finally:
                connections.close_all()

        with (
            patch.object(Lead, "full_clean", validated_together),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            return list(pool.map(submit, payloads))

    def test_simultaneous_identical_submissions_create_one_record_and_event(self):
        payload = inquiry_payload()
        results = self.race([payload, payload.copy()])
        self.assertEqual(results[0][0], results[1][0])
        self.assertCountEqual([result[1] for result in results], [True, False])
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(ActivityEvent.objects.count(), 1)

    def test_simultaneous_different_payloads_under_one_key_have_one_conflict(self):
        payload = inquiry_payload()
        results = self.race([payload, {**payload, "name": "Different synthetic customer"}])
        self.assertEqual(sum(result[0] == "conflict" for result in results), 1)
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(ActivityEvent.objects.count(), 1)
