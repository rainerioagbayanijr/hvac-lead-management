from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from crm.models import Lead
from crm.services import create_inquiry
from crm.workflow import (
    add_note,
    assign_lead,
    change_stage,
    claim_lead,
    create_manual_lead,
    record_contact,
    reopen_lead,
)
from operations.rate_limits import client_ip, consume_limit

from .serializers import (
    AssignmentSerializer,
    ClaimSerializer,
    ContactSerializer,
    InquirySerializer,
    LeadDetailSerializer,
    LeadListSerializer,
    ManualLeadSerializer,
    NoteSerializer,
    ReopenSerializer,
    StageSerializer,
)

User = get_user_model()


@method_decorator(csrf_protect, name="dispatch")
class InquiryView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        consume_limit("inquiry_ip", client_ip(request), settings.PUBLIC_INQUIRIES_PER_HOUR, 3600)
        serializer = InquirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead, created = create_inquiry(serializer.validated_data)
        return Response({"reference": str(lead.id)}, status=201 if created else 200)


class LeadListView(generics.ListAPIView):
    serializer_class = LeadListSerializer
    queryset = Lead.objects.select_related("owner").all()

    def post(self, request):
        serializer = ManualLeadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead = create_manual_lead(request.user, serializer.validated_data)
        return Response(
            LeadDetailSerializer(lead, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class LeadDetailView(generics.RetrieveAPIView):
    serializer_class = LeadDetailSerializer
    queryset = Lead.objects.select_related("owner").prefetch_related("activity__actor").all()


class TeamView(APIView):
    def get(self, request):
        if request.user.role != User.Role.ADMIN:
            raise PermissionDenied("Only an admin can view assignment options.")
        users = User.objects.filter(is_active=True).order_by("first_name", "username")
        return Response(
            [
                {"id": user.pk, "display_name": user.display_name, "role": user.role}
                for user in users
            ]
        )


class LeadActionView(APIView):
    serializer_class = None
    action = None

    def post(self, request, pk):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        lead = self.action(pk, request.user, values)
        lead = (
            Lead.objects.select_related("owner").prefetch_related("activity__actor").get(pk=lead.pk)
        )
        return Response(LeadDetailSerializer(lead, context={"request": request}).data)


class ClaimLeadView(LeadActionView):
    serializer_class = ClaimSerializer
    action = staticmethod(
        lambda pk, actor, values: claim_lead(
            pk, actor, values["action_key"], values["expected_version"]
        )
    )


class AssignLeadView(LeadActionView):
    serializer_class = AssignmentSerializer
    action = staticmethod(
        lambda pk, actor, values: assign_lead(
            pk,
            actor,
            values["action_key"],
            values["expected_version"],
            values["owner_id"],
        )
    )


class RecordContactView(LeadActionView):
    serializer_class = ContactSerializer
    action = staticmethod(
        lambda pk, actor, values: record_contact(
            pk,
            actor,
            values["action_key"],
            values["expected_version"],
            values["method"],
            values["summary"],
        )
    )


class ChangeStageView(LeadActionView):
    serializer_class = StageSerializer
    action = staticmethod(
        lambda pk, actor, values: change_stage(
            pk,
            actor,
            values["action_key"],
            values["expected_version"],
            values["stage"],
            values.get("quote_amount"),
            values["loss_reason"],
        )
    )


class ReopenLeadView(LeadActionView):
    serializer_class = ReopenSerializer
    action = staticmethod(
        lambda pk, actor, values: reopen_lead(
            pk,
            actor,
            values["action_key"],
            values["expected_version"],
            values["stage"],
        )
    )


class AddNoteView(LeadActionView):
    serializer_class = NoteSerializer
    action = staticmethod(
        lambda pk, actor, values: add_note(
            pk,
            actor,
            values["action_key"],
            values["expected_version"],
            values["body"],
        )
    )
