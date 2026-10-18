"""Deterministic provider for local and public demo environments."""

from dataclasses import dataclass

from django.utils import timezone


@dataclass(frozen=True)
class SendResult:
    provider_message_id: str
    http_status: int = 202
    delivered_at: object = None


class FakeEmailAdapter:
    def send(self, execution):
        return SendResult(
            provider_message_id=f"demo-{execution.id}",
            delivered_at=timezone.now(),
        )
