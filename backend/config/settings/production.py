"""Fail-closed settings for the single-origin production deployment."""

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

if len(SECRET_KEY) < 50:  # noqa: F405
    raise ImproperlyConfigured("Production DJANGO_SECRET_KEY must contain at least 50 characters.")
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("Production requires explicit DJANGO_ALLOWED_HOSTS.")
if os.environ.get("POSTGRES_SSLMODE") not in {"require", "verify-ca", "verify-full"}:
    raise ImproperlyConfigured("Production requires an explicit secure POSTGRES_SSLMODE.")

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 3600
# Enable only when the chosen ingress strips untrusted forwarded-proto headers.
if os.environ.get("DJANGO_TRUST_PROXY", "false").lower() == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
