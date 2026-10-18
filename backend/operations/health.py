import logging

from django.db import DatabaseError, connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    http_method_names = ["get", "head", "options"]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            logger.warning("Database readiness failed; request_id=%s", request.request_id)
            response = Response({"status": "unavailable"}, status=503)
        else:
            response = Response({"status": "ok"})
        response["Cache-Control"] = "no-store"
        return response
