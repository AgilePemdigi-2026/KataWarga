"""
KataWarga — Production settings.
Digunakan saat deployment ke Coolify / Docker container di https://katawarga.caiis.ai.id/
"""
import os
from .base import *  # noqa: F401, F403

# Production mode
DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 't')

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-prod-placeholder-replace-via-coolify-env-var-xyz987',
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

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

# Static files serving with WhiteNoise
# WhiteNoiseMiddleware must be right after SecurityMiddleware
try:
    import whitenoise  # noqa: F401
    if 'whitenoise.middleware.WhiteNoiseMiddleware' not in MIDDLEWARE:
        sec_idx = MIDDLEWARE.index('django.middleware.security.SecurityMiddleware')
        MIDDLEWARE.insert(sec_idx + 1, 'whitenoise.middleware.WhiteNoiseMiddleware')
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
except ImportError:
    # Fallback saat pengujian lokal tanpa paket whitenoise
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

STATIC_ROOT = BASE_DIR / 'staticfiles'

# Database configuration (Coolify PostgreSQL integration)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', os.environ.get('POSTGRES_DB', 'katawarga')),
        'USER': os.environ.get('DB_USER', os.environ.get('POSTGRES_USER', 'postgres')),
        'PASSWORD': os.environ.get('DB_PASSWORD', os.environ.get('POSTGRES_PASSWORD', 'postgres')),
        'HOST': os.environ.get('DB_HOST', os.environ.get('POSTGRES_HOST', '127.0.0.1')),
        'PORT': os.environ.get('DB_PORT', os.environ.get('POSTGRES_PORT', '5432')),
    }
}
