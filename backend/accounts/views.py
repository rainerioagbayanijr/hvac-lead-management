from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from operations.rate_limits import client_ip, consume_limit


def session_payload(user):
    if not user.is_authenticated:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "user": {
            "id": user.pk,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
        },
        "capabilities": {
            "view_leads": True,
            "manage_accounts": user.is_superuser,
            "assign_leads": user.role == user.Role.ADMIN,
        },
    }


class CsrfView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrf_token": get_token(request._request)})


class SessionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(session_payload(request.user))


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=1024, trim_whitespace=False)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        consume_limit("login_ip", client_ip(request), settings.LOGIN_ATTEMPTS_PER_IP, 900)
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        consume_limit(
            "login_account", values["username"].casefold(), settings.LOGIN_ATTEMPTS_PER_ACCOUNT, 900
        )
        form = AuthenticationForm(request=request._request, data=values)
        if not form.is_valid():
            raise AuthenticationFailed()
        login(request._request, form.get_user())
        # Fixed expiry, rather than extending the session on each ordinary request.
        request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        return Response(session_payload(form.get_user()))


@method_decorator(csrf_protect, name="dispatch")
class LogoutView(APIView):
    def post(self, request):
        logout(request._request)
        return Response({"authenticated": False})
