"""Create local test accounts without fixed passwords or overwriting real users."""

import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Create local-only accounts and write generated passwords to ignored .local-accounts.md."

    def handle(self, *args, **options):
        if not settings.DEBUG or settings.DATABASES["default"]["HOST"] not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise CommandError(
                "Development accounts are allowed only with DEBUG and a local database."
            )
        destination = settings.BASE_DIR.parent / ".local-accounts.md"
        if destination.exists():
            self.stdout.write(
                "Local account notes already exist; accounts and passwords were left unchanged."
            )
            return
        rows = []
        with transaction.atomic():
            for username, role, display_name in [
                ("demo_admin", "admin", "Demo Owner"),
                ("demo_staff", "staff", "Demo Office"),
            ]:
                if get_user_model().objects.filter(username=username).exists():
                    rows.append(f"| {username} | {role} | Existing account; password unchanged |")
                    continue
                password = secrets.token_urlsafe(24)
                create = (
                    get_user_model().objects.create_superuser
                    if role == "admin"
                    else get_user_model().objects.create_user
                )
                create(
                    username=username,
                    password=password,
                    first_name=display_name,
                    role=role,
                    email=f"{username}@example.test",
                )
                rows.append(f"| {username} | {role} | {password} |")
            notes = (
                "# Local development accounts\n\n"
                "Use only at http://127.0.0.1:5173/login. Keep this ignored file private.\n"
                "These accounts are not deployed public-demo credentials.\n\n"
                "| Username | Role | Password |\n| --- | --- | --- |\n" + "\n".join(rows) + "\n"
            )
            try:
                with destination.open("x", encoding="utf-8") as output:
                    output.write(notes)
            except OSError as exc:
                raise CommandError(
                    "Could not save local account notes; new accounts were rolled back."
                ) from exc
        self.stdout.write(
            "Local accounts are ready. Passwords are in ignored .local-accounts.md, not printed."
        )
