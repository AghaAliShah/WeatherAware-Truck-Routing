"""Django settings. Everything environment-specific comes from env vars."""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes"}


DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    # The service is stateless (no sessions, no signed cookies), so an ephemeral per-process key is
    # safe and lets a fresh deploy start without configuration. Set DJANGO_SECRET_KEY to pin one.
    SECRET_KEY = "dev-only-insecure-key" if DEBUG else secrets.token_urlsafe(50)

ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]
if DEBUG:
    ALLOWED_HOSTS += ["localhost", "127.0.0.1", "[::1]"]
# Platforms that tell the container its public hostname (Render, Hugging Face Spaces).
for _var in ("RENDER_EXTERNAL_HOSTNAME", "SPACE_HOST"):
    if os.environ.get(_var):
        ALLOWED_HOSTS.append(os.environ[_var])
# Vercel: production alias, per-branch and per-deployment hostnames, plus the shared suffix.
for _var in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
    if os.environ.get(_var):
        ALLOWED_HOSTS.append(os.environ[_var])
if os.environ.get("VERCEL"):
    ALLOWED_HOSTS.append(".vercel.app")
if os.environ.get("SPACE_ID"):  # Hugging Face: also serve the huggingface.co embed and *.hf.space
    ALLOWED_HOSTS += [".hf.space", "huggingface.co"]

INSTALLED_APPS = ["rest_framework", "routing"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# The service is stateless: no database is needed.
DATABASES = {}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# The built React app is copied here by the Docker build and served at "/".
FRONTEND_DIR = BASE_DIR / "static_frontend"
if FRONTEND_DIR.is_dir():
    WHITENOISE_ROOT = FRONTEND_DIR
    WHITENOISE_INDEX_FILE = True

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.environ.get("API_THROTTLE", "60/min"),
        "plan": os.environ.get("API_THROTTLE_PLAN", "20/min"),
        "events": os.environ.get("API_THROTTLE_EVENTS", "120/min"),
    },
    "EXCEPTION_HANDLER": "routing.errors.exception_handler",
}

# --- Third-party services (all key-less by default) -------------------------
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "")
USER_AGENT = f"weather-aware-truck-routing/1.0 ({CONTACT_EMAIL or 'assessment project'})"
OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org")
PHOTON_URL = os.environ.get("PHOTON_URL", "https://photon.komoot.io")
NOMINATIM_URL = os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
OPEN_METEO_URL = os.environ.get("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
UPSTREAM_TIMEOUT_S = float(os.environ.get("UPSTREAM_TIMEOUT_S", "25"))

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"

# --- Experimentation ---------------------------------------------------------
# Serverless filesystems are read-only except /tmp (telemetry is also written to stdout logs).
TELEMETRY_DIR = os.environ.get("TELEMETRY_DIR", "/tmp/telemetry" if os.environ.get("VERCEL") else str(BASE_DIR / "var"))
SHADOW_ENABLED = env_bool("SHADOW_ENABLED", True)
EVENTS_ENABLED = env_bool("EVENTS_ENABLED", True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"telemetry": {"handlers": ["console"], "level": "INFO", "propagate": False}},
}
