from decimal import Decimal

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from crm.models import ActivityEvent, Lead


class InquirySerializer(serializers.Serializer):
    submission_key = serializers.UUIDField()
    name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=40, allow_blank=True, default="")
    email = serializers.EmailField(allow_blank=True, default="")
    location = serializers.CharField(max_length=250, allow_blank=True, default="")
    service_type = serializers.ChoiceField(choices=Lead.Service.choices)
    requirements = serializers.CharField(max_length=4000, allow_blank=True, default="")
    privacy_acknowledged = serializers.BooleanField()
    company_website = serializers.CharField(allow_blank=True, default="", max_length=250)

    def validate(self, attrs):
        unknown = set(self.initial_data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(
                {key: ["This field is not accepted."] for key in sorted(unknown)}
            )
        if attrs["company_website"]:
            raise serializers.ValidationError(
                {"non_field_errors": ["The inquiry could not be accepted."]}
            )
        if not attrs["privacy_acknowledged"]:
            raise serializers.ValidationError(
                {"privacy_acknowledged": ["Read and acknowledge the privacy notice."]}
            )
        attrs["email"] = attrs["email"].lower()
        if not attrs["phone"] and not attrs["email"]:
            raise serializers.ValidationError(
                {"phone": ["Provide a phone number or email address."]}
            )
        if attrs["phone"] and not any(character.isdigit() for character in attrs["phone"]):
            raise serializers.ValidationError(
                {"phone": ["Enter a phone number containing digits."]}
            )
        return attrs


class LeadListSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.display_name", default=None, read_only=True)
    owner_id = serializers.IntegerField(read_only=True)
    service_label = serializers.CharField(source="get_service_type_display", read_only=True)
    stage_label = serializers.CharField(source="get_stage_display", read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id",
            "name",
            "phone",
            "email",
            "service_type",
            "service_label",
            "stage",
            "stage_label",
            "owner_name",
            "owner_id",
            "source",
            "received_at",
        ]


class ActivitySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.display_name", default=None, read_only=True)
    summary = serializers.SerializerMethodField()

    class Meta:
        model = ActivityEvent
        fields = ["id", "event_type", "occurred_at", "actor_name", "summary"]

    def get_summary(self, event):
        data = event.metadata
        if event.event_type == "created":
            return "Inquiry received from the website."
        if event.event_type == "manual_created":
            return f"Inquiry added manually from {data.get('source', 'another source')}."
        if event.event_type == "claimed":
            return f"Claimed by {data.get('owner_name', 'a team member')}."
        if event.event_type == "assigned":
            owner = data.get("owner_name")
            return f"Assigned to {owner}." if owner else "Assignment removed."
        if event.event_type == "contact_recorded":
            method = data.get("method", "contact")
            stage_change = (
                " The lead moved to Contacted." if data.get("stage_from") == "new" else ""
            )
            summary = data.get("summary", "")
            suffix = f" {summary}" if summary else ""
            return f"{method.title()} recorded.{stage_change}{suffix}"
        if event.event_type == "stage_changed":
            before = data.get("stage_from", "")
            after = data.get("stage_to", "")
            if after == "lost":
                return f"Marked Lost: {data.get('loss_reason', '')}"
            if after == "quoted":
                return (
                    f"Moved from {before.title()} to Quoted · SGD {data.get('quote_amount', '')}."
                )
            return f"Moved from {before.title()} to {after.title()}."
        if event.event_type == "lead_reopened":
            return f"Reopened at {data.get('stage_to', '').title()}."
        if event.event_type == "note_added":
            return data.get("body", "Note added.")
        return "Lead activity recorded."


class LeadDetailSerializer(LeadListSerializer):
    activity = ActivitySerializer(many=True, read_only=True)

    class Meta(LeadListSerializer.Meta):
        fields = LeadListSerializer.Meta.fields + [
            "location",
            "requirements",
            "created_at",
            "updated_at",
            "version",
            "activity",
            "first_contact_at",
            "quote_amount",
            "loss_reason",
            "closed_at",
        ]


class StrictSerializer(serializers.Serializer):
    def validate(self, attrs):
        unknown = set(self.initial_data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(
                {key: ["This field is not accepted."] for key in sorted(unknown)}
            )
        return attrs


class LeadActionSerializer(StrictSerializer):
    action_key = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=1)


class ClaimSerializer(LeadActionSerializer):
    pass


class AssignmentSerializer(LeadActionSerializer):
    owner_id = serializers.IntegerField(allow_null=True)


class ContactSerializer(LeadActionSerializer):
    method = serializers.ChoiceField(choices=["phone", "email", "whatsapp", "other"])
    summary = serializers.CharField(max_length=1000, allow_blank=True, default="")


class StageSerializer(LeadActionSerializer):
    stage = serializers.ChoiceField(choices=Lead.Stage.choices)
    quote_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01"), required=False, allow_null=True
    )
    loss_reason = serializers.CharField(max_length=500, allow_blank=True, default="")


class ReopenSerializer(LeadActionSerializer):
    stage = serializers.ChoiceField(
        choices=[Lead.Stage.NEW, Lead.Stage.CONTACTED, Lead.Stage.QUOTED]
    )


class NoteSerializer(LeadActionSerializer):
    body = serializers.CharField(max_length=2000)


class ManualLeadSerializer(StrictSerializer):
    name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=40, allow_blank=True, default="")
    email = serializers.EmailField(allow_blank=True, default="")
    location = serializers.CharField(max_length=250, allow_blank=True, default="")
    service_type = serializers.ChoiceField(choices=Lead.Service.choices)
    requirements = serializers.CharField(max_length=4000, allow_blank=True, default="")
    source = serializers.ChoiceField(choices=Lead.Source.choices)
    received_at = serializers.DateTimeField(required=False, default=None)

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Enter a customer name.")
        return value

    def validate_phone(self, value):
        value = value.strip()
        if value and not any(character.isdigit() for character in value):
            raise serializers.ValidationError("Enter a phone number containing digits.")
        return value

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs["phone"] and not attrs["email"]:
            raise serializers.ValidationError(
                {"phone": ["Provide a phone number or email address."]}
            )
        raw_time = self.initial_data.get("received_at")
        if raw_time not in (None, ""):
            parsed = parse_datetime(raw_time) if isinstance(raw_time, str) else raw_time
            if parsed is None or timezone.is_naive(parsed):
                raise serializers.ValidationError(
                    {"received_at": ["Include a time-zone offset, such as +08:00."]}
                )
            if parsed > timezone.now():
                raise serializers.ValidationError(
                    {"received_at": ["Receipt time cannot be in the future."]}
                )
        return attrs
