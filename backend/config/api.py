import logging

from django.http import Http404, JsonResponse
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class Conflict(exceptions.APIException):
    status_code = 409
    default_detail = "This submission key was already used with different details."
    default_code = "submission_conflict"


def json_error(request, code, message, status):
    return JsonResponse(
        {"code": code, "message": message, "request_id": getattr(request, "request_id", None)},
        status=status,
    )


def csrf_failure(request, reason=""):
    return json_error(request, "csrf_failed", "Refresh the page and try again.", 403)


def api_exception_handler(exc, context):
    """Keep framework errors predictable without exposing unexpected exceptions."""
    response = exception_handler(exc, context)
    request = context.get("request")
    if response is None:
        request_id = getattr(request, "request_id", None)
        logger.error("Unhandled API exception: %s; request_id=%s", type(exc).__name__, request_id)
        return Response(
            {
                "code": "internal_error",
                "message": "An unexpected error occurred. Try again later.",
                "request_id": request_id,
            },
            status=500,
        )

    code = "request_error"
    message = "The request could not be completed."
    fields = None
    if isinstance(exc, exceptions.ValidationError):
        code, message, fields = "validation_error", "Check the submitted fields.", response.data
    elif isinstance(exc, exceptions.NotAuthenticated):
        code, message = "not_authenticated", "Please log in to continue."
    elif isinstance(exc, exceptions.PermissionDenied):
        code = "csrf_failed" if str(exc.detail).startswith("CSRF Failed:") else "permission_denied"
        message = "Refresh the page and try again." if code == "csrf_failed" else "Access denied."
    elif isinstance(exc, (exceptions.NotFound, Http404)):
        code, message = "not_found", "The requested record is unavailable."
    elif isinstance(exc, exceptions.Throttled):
        code, message = "rate_limited", "Too many requests. Try again later."
    elif isinstance(exc, exceptions.ParseError):
        code, message = "invalid_request", "The request body is invalid."
    elif isinstance(exc, exceptions.MethodNotAllowed):
        code, message = "method_not_allowed", "This method is not supported."
    elif isinstance(exc, Conflict):
        code, message = exc.default_code, str(exc.detail)
    elif isinstance(exc, exceptions.AuthenticationFailed):
        code, message = "invalid_credentials", "The username or password is incorrect."

    response.data = {
        "code": code,
        "message": message,
        "request_id": getattr(request, "request_id", None),
    }
    if fields is not None:
        response.data["fields"] = fields
    return response
