import csv

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from crm.metrics import dashboard_metrics
from crm.models import FollowUpTask, Lead
from crm.queries import filtered_leads
from crm.services import create_inquiry
from crm.tasks import cancel_task, complete_task, reschedule_task, schedule_task
from crm.workflow import (
    add_note,
    archive_lead,
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
    FollowUpTaskSerializer,
    InquirySerializer,
    LeadActionSerializer,
    LeadDetailSerializer,
    LeadListSerializer,
    ManualLeadSerializer,
    NoteSerializer,
    ReopenSerializer,
    StageSerializer,
    TaskActionSerializer,
    TaskRescheduleSerializer,
    TaskScheduleSerializer,
)

User = get_user_model()


@method_decorator(csrf_protect, name="dispatch")
class InquiryView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        if settings.DEMO_MODE:
            return Response(
                {
                    "code": "demo_read_only",
                    "message": "Public inquiry intake is disabled in the synthetic-data demo.",
                },
                status=403,
            )
        consume_limit("inquiry_ip", client_ip(request), settings.PUBLIC_INQUIRIES_PER_HOUR, 3600)
        serializer = InquirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead, created = create_inquiry(serializer.validated_data)
        return Response({"reference": str(lead.id)}, status=201 if created else 200)


class LeadListView(generics.ListAPIView):
    serializer_class = LeadListSerializer

    def get_queryset(self):
        return filtered_leads(self.request.query_params, self.request.user)

    def post(self, request):
        serializer = ManualLeadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead = create_manual_lead(request.user, serializer.validated_data)
        return Response(
            LeadDetailSerializer(lead, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


def export_safe_cell(value):
    text = "" if value is None else str(value)
    first = text.lstrip(" \t\r\n")[:1]
    return f"'{text}" if first in {"=", "+", "-", "@"} else text


class LeadExportView(APIView):
    def get(self, request):
        if request.user.role != User.Role.ADMIN:
            raise PermissionDenied("Only an admin can export customer inquiries.")
        leads = filtered_leads(request.query_params, request.user)
        if leads.count() > 10000:
            raise ValidationError(
                {"export": ["Narrow the filters to export 10,000 leads or fewer."]}
            )
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="service-inquiries.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Reference",
                "Customer",
                "Phone",
                "Email",
                "Location",
                "Service",
                "Source",
                "Stage",
                "Owner",
                "Received at",
                "First contact at",
                "Quote SGD",
            ]
        )
        for lead in leads[:10000]:
            writer.writerow(
                [
                    export_safe_cell(lead.pk),
                    export_safe_cell(lead.name),
                    export_safe_cell(lead.phone),
                    export_safe_cell(lead.email),
                    export_safe_cell(lead.location),
                    export_safe_cell(lead.get_service_type_display()),
                    export_safe_cell(lead.source),
                    export_safe_cell(lead.get_stage_display()),
                    export_safe_cell(lead.owner.display_name if lead.owner_id else "Unassigned"),
                    export_safe_cell(lead.received_at.isoformat()),
                    export_safe_cell(
                        lead.first_contact_at.isoformat() if lead.first_contact_at else ""
                    ),
                    export_safe_cell(lead.quote_amount),
                ]
            )
        response["Cache-Control"] = "no-store"
        return response


class LeadDetailView(generics.RetrieveAPIView):
    serializer_class = LeadDetailSerializer

    def get_queryset(self):
        queryset = Lead.objects.select_related("owner").prefetch_related("activity__actor", "tasks")
        if self.request.user.role != User.Role.ADMIN:
            queryset = queryset.filter(archived_at__isnull=True)
        return queryset


class ArchiveLeadView(APIView):
    restore = False

    def post(self, request, pk):
        serializer = LeadActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        lead = archive_lead(
            pk,
            request.user,
            values["action_key"],
            values["expected_version"],
            restore=self.restore,
        )
        lead = (
            Lead.objects.select_related("owner")
            .prefetch_related("activity__actor", "tasks")
            .get(pk=lead.pk)
        )
        return Response(LeadDetailSerializer(lead, context={"request": request}).data)


class RestoreLeadView(ArchiveLeadView):
    restore = True


class TaskListView(generics.ListAPIView):
    serializer_class = FollowUpTaskSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        queryset = FollowUpTask.objects.select_related("lead", "lead__owner")
        task_status = self.request.query_params.get("status", "pending")
        if task_status not in FollowUpTask.Status.values:
            raise ValidationError({"status": ["Choose pending, completed, or cancelled."]})
        queryset = queryset.filter(status=task_status)
        due_filter = self.request.query_params.get("due", "")
        now = timezone.now()
        if due_filter == "overdue":
            if task_status != FollowUpTask.Status.PENDING:
                raise ValidationError({"due": ["Overdue applies only to pending follow-ups."]})
            queryset = queryset.filter(due_at__lt=now)
        elif due_filter == "today":
            today = timezone.localdate()
            queryset = queryset.filter(due_at__date=today)
        elif due_filter and due_filter != "all":
            raise ValidationError({"due": ["Choose overdue, today, or all."]})
        return queryset.order_by("due_at", "id")


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


class DashboardView(APIView):
    def get(self, request):
        return Response(dashboard_metrics())


class LeadActionView(APIView):
    serializer_class = None
    action = None

    def post(self, request, pk):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        lead = self.action(pk, request.user, values)
        lead = (
            Lead.objects.select_related("owner")
            .prefetch_related("activity__actor", "tasks")
            .get(pk=lead.pk)
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


class ScheduleTaskView(LeadActionView):
    serializer_class = TaskScheduleSerializer
    action = staticmethod(
        lambda pk, actor, values: schedule_task(
            pk,
            actor,
            values["action_key"],
            values["expected_version"],
            values["title"],
            values["details"],
            values["due_at"],
        )
    )


class TaskActionView(APIView):
    serializer_class = TaskActionSerializer
    action = None

    def post(self, request, lead_pk, task_pk):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        lead = self.action(
            lead_pk,
            task_pk,
            request.user,
            values["action_key"],
            values["expected_version"],
        )
        lead = (
            Lead.objects.select_related("owner")
            .prefetch_related("activity__actor", "tasks")
            .get(pk=lead.pk)
        )
        return Response(LeadDetailSerializer(lead, context={"request": request}).data)


class RescheduleTaskView(TaskActionView):
    serializer_class = TaskRescheduleSerializer
    action = staticmethod(
        lambda lead_pk, task_pk, actor, action_key, expected_version, due_at=None: reschedule_task(
            lead_pk, task_pk, actor, action_key, expected_version, due_at
        )
    )

    def post(self, request, lead_pk, task_pk):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        lead = self.action(
            lead_pk,
            task_pk,
            request.user,
            values["action_key"],
            values["expected_version"],
            values["due_at"],
        )
        lead = (
            Lead.objects.select_related("owner")
            .prefetch_related("activity__actor", "tasks")
            .get(pk=lead.pk)
        )
        return Response(LeadDetailSerializer(lead, context={"request": request}).data)


class CompleteTaskView(TaskActionView):
    action = staticmethod(complete_task)


class CancelTaskView(TaskActionView):
    action = staticmethod(cancel_task)
