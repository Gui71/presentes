import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)


def boolean(name, default=False):
    value = os.getenv(name, str(default)).strip().lower()
    if value not in {"true", "false", "1", "0", "yes", "no"}:
        raise ImproperlyConfigured(f"{name} deve ser true ou false.")
    return value in {"true", "1", "yes"}


def csv(name, default=""):
    return [part.strip() for part in os.getenv(name, default).split(",") if part.strip()]

TRUSTED_PROXY_IPS = csv("TRUSTED_PROXY_IPS")

APP_ENV = os.getenv("APP_ENV", "production")
if APP_ENV not in {"development", "production", "test"}:
    raise ImproperlyConfigured("APP_ENV inválido.")
PRODUCTION = APP_ENV == "production"
DEBUG = boolean("DEBUG", False)
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY.lower().startswith(("change-me", "django-insecure", "example")):
    raise ImproperlyConfigured("Defina uma SECRET_KEY própria no ambiente ou em .env.")
if PRODUCTION and (DEBUG or len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5):
    raise ImproperlyConfigured("Produção exige DEBUG=false e SECRET_KEY forte (50+ caracteres).")
ALLOWED_HOSTS = csv("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = csv("CSRF_TRUSTED_ORIGINS")
if PRODUCTION and (not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS):
    raise ImproperlyConfigured("Defina ALLOWED_HOSTS explícitos em produção.")
if PRODUCTION and (not CSRF_TRUSTED_ORIGINS or any(not value.startswith("https://") or "*" in value for value in CSRF_TRUSTED_ORIGINS)):
    raise ImproperlyConfigured("Defina CSRF_TRUSTED_ORIGINS HTTPS explícitas em produção.")

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "axes", "gifts.apps.GiftsConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "gifts.middleware.PrivatePagesMiddleware",
    "axes.middleware.AxesMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request", "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": BASE_DIR / os.getenv("DATABASE_PATH", "db.sqlite3"),
    "OPTIONS": {"timeout": 20},
    "TEST": {"NAME": os.getenv("TEST_DATABASE_PATH", str(BASE_DIR / ".test.sqlite3"))},
}}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTHENTICATION_BACKENDS = ["axes.backends.AxesStandaloneBackend", "django.contrib.auth.backends.ModelBackend"]
# Database handler compartilha contadores entre workers; não confia em X-Forwarded-For.
AXES_HANDLER = "axes.handlers.database.AxesDatabaseHandler"
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = ["ip_address"]
AXES_RESET_ON_SUCCESS = True
AXES_CLIENT_IP_CALLABLE = "gifts.security.client_ip"
AXES_LOCKOUT_TEMPLATE = "lockout.html"
AXES_ENABLE_ACCESS_FAILURE_LOG = False
# Não incluir nomes, IPs, senhas ou identificadores nos logs do bloqueador.
LOGGING = {"version": 1, "disable_existing_loggers": False,
           "handlers": {"discard": {"class": "logging.NullHandler"}},
           "loggers": {"axes": {"handlers": ["discard"], "propagate": False}}}
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / os.getenv("STATIC_ROOT", "staticfiles")
MEDIA_ROOT = BASE_DIR / os.getenv("MEDIA_ROOT", "media")
MEDIA_URL = "/media/"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "panel"
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = PRODUCTION
CSRF_COOKIE_SECURE = PRODUCTION
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_SSL_REDIRECT = PRODUCTION
SECURE_REDIRECT_EXEMPT = [r"healthz/$"]
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = boolean("SECURE_HSTS_INCLUDE_SUBDOMAINS")
SECURE_HSTS_PRELOAD = boolean("SECURE_HSTS_PRELOAD")
if boolean("TRUST_PROXY_HTTPS"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
DATA_UPLOAD_MAX_MEMORY_SIZE = 64 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100
