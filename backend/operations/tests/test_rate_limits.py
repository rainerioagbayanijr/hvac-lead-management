from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.db import connections
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import Throttled

from operations.models import RateLimitBucket
from operations.rate_limits import client_ip, consume_limit


class RateLimitTests(TestCase):
    def test_counter_is_hashed_and_resets_in_next_window(self):
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        consume_limit("test", "synthetic-client", 1, 3600, now=now)
        with self.assertRaises(Throttled):
            consume_limit("test", "synthetic-client", 1, 3600, now=now)
        bucket = RateLimitBucket.objects.get()
        self.assertNotEqual(bucket.subject_hash, "synthetic-client")
        self.assertEqual(bucket.count, 1)
        consume_limit("test", "synthetic-client", 1, 3600, now=now + timedelta(hours=1))
        self.assertEqual(RateLimitBucket.objects.count(), 2)

    def test_untrusted_forwarded_header_does_not_change_ip(self):
        request = RequestFactory().get(
            "/", REMOTE_ADDR="192.0.2.10", HTTP_X_FORWARDED_FOR="198.51.100.5"
        )
        self.assertEqual(client_ip(request), "192.0.2.10")

    @override_settings(TRUSTED_PROXY_IPS=["192.0.2.10"])
    def test_trusted_proxy_uses_rightmost_untrusted_hop(self):
        request = RequestFactory().get(
            "/", REMOTE_ADDR="192.0.2.10", HTTP_X_FORWARDED_FOR="203.0.113.99, 198.51.100.5"
        )
        self.assertEqual(client_ip(request), "198.51.100.5")


class ConcurrentRateLimitTests(TransactionTestCase):
    def test_concurrent_requests_cannot_exceed_bucket_limit(self):
        barrier = Barrier(2)
        now = timezone.now()

        def attempt():
            connections.close_all()
            try:
                barrier.wait(timeout=5)
                consume_limit("race", "synthetic-client", 1, 3600, now=now)
                return "allowed"
            except Throttled:
                return "blocked"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))
        self.assertCountEqual(results, ["allowed", "blocked"])
        self.assertEqual(RateLimitBucket.objects.get().count, 1)
