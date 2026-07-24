"""
Development settings
"""
from .base import *
from decouple import config

DEBUG = True

# Use real SMTP locally when EMAIL_BACKEND is set in .env.
# Fall back to console output for developers who have not configured SMTP.
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend',
)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='webmaster@localhost')
