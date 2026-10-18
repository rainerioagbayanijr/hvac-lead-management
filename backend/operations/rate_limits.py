import ipaddress
import math
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import Throttled

from .models import RateLimitBucket


def client_ip(request):
    address = request.META.get("REMOTE_ADDR", "")
    if address in settings.TRUSTED_PROXY_IPS:
        chain = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
        for candidate in reversed(chain):
            candidate = candidate.strip()
            if candidate and candidate not in settings.TRUSTED_PROXY_IPS:
                address = candidate
                break
    try:
        return str(ipaddress.ip_address(address))
    except ValueError:
        return "unknown"


def consume_limit(scope, subject, limit, window_seconds, *, now=None):
    """Serialize counters in PostgreSQL; never store raw IPs or usernames."""
    now = now or timezone.now()
    start = datetime.fromtimestamp(
        math.floor(now.timestamp() / window_seconds) * window_seconds, tz=UTC
    )
    expires = start + timedelta(seconds=window_seconds)
    subject_hash = salted_hmac("lead-followup.rate-limit", subject, algorithm="sha256").hexdigest()
    with transaction.atomic():
        bucket, _ = RateLimitBucket.objects.get_or_create(
            scope=scope,
            subject_hash=subject_hash,
            bucket_start=start,
            defaults={"expires_at": expires},
        )
        bucket = RateLimitBucket.objects.select_for_update().get(pk=bucket.pk)
        if bucket.count >= limit:
            raise Throttled(wait=max(1, math.ceil((expires - now).total_seconds())))
        bucket.count += 1
        bucket.save(update_fields=["count"])
