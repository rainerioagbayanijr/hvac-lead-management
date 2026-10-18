from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.models import EmailExecution, WorkerHeartbeat
from integrations.services import request_manual_retry

from .serializers import EmailExecutionSerializer

User = get_user_model()


class IsBusinessAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.role == User.Role.ADMIN
        )


class IntegrationStatusView(APIView):
    permission_classes = [IsBusinessAdmin]

    def get(self, request):
        counts = {
            item["status"]: item["total"]
            for item in EmailExecution.objects.values("status").annotate(total=Count("id"))
        }
        latest = EmailExecution.objects.order_by("-created_at").first()
        worker = WorkerHeartbeat.objects.filter(worker_name="email-executions").first()
        return Response(
            {
                "adapter": "fake" if settings.DEMO_MODE else settings.INTEGRATION_ADAPTER,
                "counts": counts,
                "latest_execution_at": latest.created_at if latest else None,
                "worker_last_success_at": worker.last_success_at if worker else None,
                "worker_fresh": bool(
                    worker
                    and worker.last_success_at
                    and worker.last_success_at >= timezone.now() - timedelta(minutes=5)
                ),
                "live_ready": bool(
                    not settings.DEMO_MODE
                    and settings.RESEND_API_KEY
                    and settings.RESEND_FROM_EMAIL
                ),
            }
        )


class PublicConfigView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"demo_mode": settings.DEMO_MODE})


class EmailExecutionListView(generics.ListAPIView):
    permission_classes = [IsBusinessAdmin]
    serializer_class = EmailExecutionSerializer
    queryset = EmailExecution.objects.select_related("lead").prefetch_related("attempts")
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        queryset = super().get_queryset()
        lead_id = self.request.query_params.get("lead", "").strip()
        return queryset.filter(lead_id=lead_id) if lead_id else queryset


class RetryExecutionView(APIView):
    permission_classes = [IsBusinessAdmin]

    def post(self, request, pk):
        execution = get_object_or_404(EmailExecution, pk=pk)
        request_manual_retry(execution)
        execution.refresh_from_db()
        return Response(EmailExecutionSerializer(execution).data)
