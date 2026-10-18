from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from crm.models import Lead
from operations.management.commands.create_demo_data import seed_demo_records


class Command(BaseCommand):
    help = "Delete and recreate synthetic demo leads; requires an explicit safety flag."

    def add_arguments(self, parser):
        parser.add_argument("--confirm-demo-reset", action="store_true")

    def handle(self, *args, **options):
        if not settings.DEMO_MODE:
            raise CommandError("Demo reset is disabled unless DEMO_MODE=true.")
        database = settings.DATABASES["default"]
        local_development = settings.DEBUG and database["HOST"] in {"localhost", "127.0.0.1", "::1"}
        named_demo_database = "demo" in database["NAME"].lower()
        isolated_test_database = connection.settings_dict["NAME"].lower().startswith("test_")
        if not (local_development or named_demo_database or isolated_test_database):
            raise CommandError(
                "Demo reset requires a local DEBUG database or a database named for demo use."
            )
        if not options["confirm_demo_reset"]:
            raise CommandError(
                "Pass --confirm-demo-reset to delete and recreate synthetic demo leads."
            )
        with transaction.atomic():
            deleted, _details = Lead.objects.filter(demo_seeded=True).delete()
            created = seed_demo_records()
        self.stdout.write(
            self.style.SUCCESS(
                f"Reset complete: removed {deleted} demo records; created {created} leads."
            )
        )
