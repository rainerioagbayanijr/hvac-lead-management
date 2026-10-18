import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from integrations.jobs import process_due
from integrations.models import WorkerHeartbeat

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process due transactional email executions. Schedule every minute."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        now = timezone.now()
        heartbeat, _created = WorkerHeartbeat.objects.get_or_create(worker_name="email-executions")
        heartbeat.last_started_at = now
        heartbeat.save(update_fields=["last_started_at"])
        try:
            count = process_due(limit=max(1, min(options["limit"], 200)))
        except Exception as exc:
            heartbeat.last_finished_at = timezone.now()
            heartbeat.last_error = type(exc).__name__
            heartbeat.save(update_fields=["last_finished_at", "last_error"])
            logger.exception("Email execution worker failed")
            raise
        heartbeat.last_finished_at = timezone.now()
        heartbeat.last_success_at = heartbeat.last_finished_at
        heartbeat.last_processed_count = count
        heartbeat.last_error = ""
        heartbeat.save(
            update_fields=[
                "last_finished_at",
                "last_success_at",
                "last_processed_count",
                "last_error",
            ]
        )
        self.stdout.write(self.style.SUCCESS(f"Processed {count} email execution(s)."))
