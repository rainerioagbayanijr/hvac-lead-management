from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from crm.models import Lead
from crm.services import create_inquiry
from operations.rate_limits import client_ip, consume_limit

from .serializers import InquirySerializer, LeadDetailSerializer, LeadListSerializer


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


class LeadDetailView(generics.RetrieveAPIView):
    serializer_class = LeadDetailSerializer
    queryset = Lead.objects.select_related("owner").prefetch_related("activity").all()
