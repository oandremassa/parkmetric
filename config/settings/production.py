import os
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

from .base import *

SECRET_KEY = env("SECRET_KEY", required=True)
DEBUG = False


def _csv_env(name):
    return [item.strip() for item in env(name, "").split(",") if item.strip()]


# Railway provides the public domain automatically. Explicit values remain useful
# for custom domains and non-Railway production deployments.
railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
app_public_url = os.getenv("APP_PUBLIC_URL", "").strip()

ALLOWED_HOSTS = _csv_env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = _csv_env("CSRF_TRUSTED_ORIGINS")

if railway_domain and railway_domain not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(railway_domain)
    CSRF_TRUSTED_ORIGINS.append(f"https://{railway_domain}")

if app_public_url:
    parsed_public_url = urlparse(app_public_url)
    if parsed_public_url.hostname and parsed_public_url.hostname not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(parsed_public_url.hostname)
    origin = f"{parsed_public_url.scheme}://{parsed_public_url.netloc}" if parsed_public_url.scheme and parsed_public_url.netloc else ""
    if origin and origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

if not os.getenv("DATABASE_URL"):
    raise ImproperlyConfigured("DATABASE_URL is required in production.")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "Set ALLOWED_HOSTS, APP_PUBLIC_URL, or deploy with RAILWAY_PUBLIC_DOMAIN available."
    )
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured(
        "Set CSRF_TRUSTED_ORIGINS, APP_PUBLIC_URL, or deploy with RAILWAY_PUBLIC_DOMAIN available."
    )

SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", True)
SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
