from django.conf import settings
from rest_framework import serializers

from integrations.models import EmailAttempt, EmailExecution


class EmailAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailAttempt
        fields = [
            "attempt_number",
            "status",
            "started_at",
            "finished_at",
            "http_status",
            "error_code",
            "error_message",
        ]


class EmailExecutionSerializer(serializers.ModelSerializer):
    lead_name = serializers.CharField(source="lead.name", read_only=True)
    lead_id = serializers.UUIDField(read_only=True)
    attempts = EmailAttemptSerializer(many=True, read_only=True)
    adapter = serializers.SerializerMethodField()

    def get_adapter(self, execution):
        return "fake" if settings.DEMO_MODE else execution.adapter

    class Meta:
        model = EmailExecution
        fields = [
            "id",
            "lead_id",
            "lead_name",
            "event_type",
            "status",
            "adapter",
            "recipient",
            "subject",
            "provider_message_id",
            "attempt_count",
            "next_attempt_at",
            "first_attempt_at",
            "accepted_at",
            "delivered_at",
            "last_error_code",
            "last_error_message",
            "created_at",
            "updated_at",
            "attempts",
        ]
