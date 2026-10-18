"""Settings shared by local and production environments."""

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[2]


def required_env(name):
    value = os.environ.get(name, "").strip()
    if not value or value.startswith("replace-with-"):
        raise ImproperlyConfigured(f"Set {name} to a real value in the environment.")
    return value


def env_list(name, default=""):
    return [value.strip() for value in os.environ.get(name, default).split(",") if value.strip()]


SECRET_KEY = required_env("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if render_hostname:
    ALLOWED_HOSTS.append(render_hostname)
    CSRF_TRUSTED_ORIGINS.append(f"https://{render_hostname}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts.apps.AccountsConfig",
    "crm.apps.CrmConfig",
    "integrations.apps.IntegrationsConfig",
    "operations.apps.OperationsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "config.middleware.RequestIdMiddleware",
    "config.middleware.ApiRequestLimitMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "static_build"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

database_url = os.environ.get("DATABASE_URL", "").strip()
if database_url:
    parsed_database_url = urlparse(database_url)
    if parsed_database_url.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured("DATABASE_URL must use PostgreSQL.")
    default_database = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed_database_url.path.lstrip("/")),
        "USER": unquote(parsed_database_url.username or ""),
        "PASSWORD": unquote(parsed_database_url.password or ""),
        "HOST": parsed_database_url.hostname or "",
        "PORT": str(parsed_database_url.port or "5432"),
        "CONN_MAX_AGE": 0,
        "OPTIONS": {
            "connect_timeout": 3,
            "sslmode": os.environ.get("POSTGRES_SSLMODE", "require"),
            "options": "-c statement_timeout=5000",
        },
    }
else:
    default_database = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": required_env("POSTGRES_DB"),
        "USER": required_env("POSTGRES_USER"),
        "PASSWORD": required_env("POSTGRES_PASSWORD"),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 0,
        "OPTIONS": {
            "connect_timeout": 3,
            "sslmode": os.environ.get("POSTGRES_SSLMODE", "disable"),
            "options": "-c statement_timeout=5000",
        },
    }
DATABASES = {"default": default_database}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "config.api.api_exception_handler",
}

LANGUAGE_CODE = "en-sg"
TIME_ZONE = "Asia/Singapore"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static_build"] if (BASE_DIR / "static_build").is_dir() else []
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
DATA_UPLOAD_MAX_MEMORY_SIZE = 64 * 1024
CSRF_FAILURE_VIEW = "config.api.csrf_failure"
# Trust forwarding headers only from explicitly configured ingress IP addresses.
TRUSTED_PROXY_IPS = env_list("DJANGO_TRUSTED_PROXY_IPS")
PUBLIC_INQUIRIES_PER_HOUR = 10
LOGIN_ATTEMPTS_PER_ACCOUNT = 10
LOGIN_ATTEMPTS_PER_IP = 30

INTEGRATION_ADAPTER = os.environ.get("INTEGRATION_ADAPTER", "fake").strip().lower()
INQUIRY_NOTIFICATION_EMAIL = os.environ.get(
    "INQUIRY_NOTIFICATION_EMAIL", "demo@example.test"
).strip()
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "").strip()
RESEND_WEBHOOK_SECRET = os.environ.get("RESEND_WEBHOOK_SECRET", "").strip()
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
