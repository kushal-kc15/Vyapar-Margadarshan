"""
Production settings for Vyapar Margadarshan.
"""
from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False

if (
    SECRET_KEY == INSECURE_SECRET_KEY
    or SECRET_KEY.startswith('django-insecure-')
    or len(SECRET_KEY) < 50
    or len(set(SECRET_KEY)) < 5
):
    raise ImproperlyConfigured('Set a strong, random SECRET_KEY in production.')

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured('Set ALLOWED_HOSTS in production.')

if not CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured('Set CORS_ALLOWED_ORIGINS in production.')

CSRF_TRUSTED_ORIGINS = config_list('CSRF_TRUSTED_ORIGINS', default='')

if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured('Set CSRF_TRUSTED_ORIGINS in production.')

SECURE_SSL_REDIRECT = config_bool('SECURE_SSL_REDIRECT', default=True)
SESSION_COOKIE_SECURE = config_bool('SESSION_COOKIE_SECURE', default=True)
CSRF_COOKIE_SECURE = config_bool('CSRF_COOKIE_SECURE', default=True)
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True)
SECURE_HSTS_PRELOAD = config_bool('SECURE_HSTS_PRELOAD', default=True)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Structured, minimal console logging.
# Uses one line per record with timestamp/level/logger/message so it is
# easy to parse from journalctl / a process manager's log capture without
# introducing file handlers, rotation, or external services.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'structured': {
            'format': '%(asctime)s level=%(levelname)s logger=%(name)s message=%(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'structured',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': config('LOG_LEVEL', default='INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': config('LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}