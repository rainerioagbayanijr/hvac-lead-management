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
            "source",
            "received_at",
        ]


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityEvent
        fields = ["id", "event_type", "occurred_at"]


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
        ]
