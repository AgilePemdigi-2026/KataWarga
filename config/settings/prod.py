"""
KataWarga — Production settings.
Digunakan saat deployment ke Coolify / Docker container di https://katawarga.caiis.ai.id/
"""
import os
from django.core.exceptions import ImproperlyConfigured
from .base import *  # noqa: F401, F403

# Production mode: WAJIB False (KW-02)
DEBUG = False

# Secret key: WAJIB disediakan melalui environment (KW-02, fail-closed)
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '').strip()
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY wajib diatur melalui environment variable untuk production."
    )

# Host & CSRF configuration
raw_hosts = os.environ.get(
    'ALLOWED_HOSTS',
    'katawarga.caiis.ai.id,localhost,127.0.0.1,0.0.0.0',
)
ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(',') if h.strip()]

raw_csrf = os.environ.get(
    'CSRF_TRUSTED_ORIGINS',
    'https://katawarga.caiis.ai.id,http://katawarga.caiis.ai.id,http://localhost:8000',
)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in raw_csrf.split(',') if o.strip()]

# Reverse proxy (Traefik / Coolify) SSL termination headers
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# Security cookies & headers
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# HSTS & SSL Redirect (dapat diaktifkan via environment variable bila proxy belum meng-enforce)
if os.environ.get('SECURE_SSL_REDIRECT', 'False').lower() in ('true', '1'):
    SECURE_SSL_REDIRECT = True
hsts_sec = os.environ.get('SECURE_HSTS_SECONDS')
if hsts_sec and hsts_sec.isdigit():
    SECURE_HSTS_SECONDS = int(hsts_sec)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Static files serving with WhiteNoise
try:
    import whitenoise  # noqa: F401
    if 'whitenoise.middleware.WhiteNoiseMiddleware' not in MIDDLEWARE:
        sec_idx = MIDDLEWARE.index('django.middleware.security.SecurityMiddleware')
        MIDDLEWARE.insert(sec_idx + 1, 'whitenoise.middleware.WhiteNoiseMiddleware')
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
except ImportError:
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

STATIC_ROOT = BASE_DIR / 'staticfiles'

# Database configuration: WAJIB disediakan melalui environment variable (tanpa default password)
db_name = os.environ.get('DB_NAME') or os.environ.get('POSTGRES_DB')
db_user = os.environ.get('DB_USER') or os.environ.get('POSTGRES_USER')
db_password = os.environ.get('DB_PASSWORD') or os.environ.get('POSTGRES_PASSWORD')
db_host = os.environ.get('DB_HOST') or os.environ.get('POSTGRES_HOST')
db_port = os.environ.get('DB_PORT') or os.environ.get('POSTGRES_PORT') or '5432'

missing_db_vars = []
if not db_name:
    missing_db_vars.append('DB_NAME (atau POSTGRES_DB)')
if not db_user:
    missing_db_vars.append('DB_USER (atau POSTGRES_USER)')
if not db_password:
    missing_db_vars.append('DB_PASSWORD (atau POSTGRES_PASSWORD)')
if not db_host:
    missing_db_vars.append('DB_HOST (atau POSTGRES_HOST)')

if missing_db_vars:
    raise ImproperlyConfigured(
        f"Kredensial database produksi tidak lengkap: {', '.join(missing_db_vars)} "
        "wajib diatur melalui environment variable."
    )

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': db_name,
        'USER': db_user,
        'PASSWORD': db_password,
        'HOST': db_host,
        'PORT': db_port,
    }
}
