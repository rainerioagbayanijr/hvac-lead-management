import uuid

from django.conf import settings

from .api import json_error


class RequestIdMiddleware:
    """Generate trusted request references; do not echo arbitrary client headers."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = str(uuid.uuid4())
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        return response


class ApiRequestLimitMiddleware:
    """Bound API bodies before JSON parsing, including anonymous requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/"):
            try:
                length = int(request.META.get("CONTENT_LENGTH") or 0)
            except ValueError:
                return json_error(request, "invalid_request", "Invalid request length.", 400)
            if length < 0 or length > settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
                return json_error(request, "payload_too_large", "The request is too large.", 413)
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store"
        return response
