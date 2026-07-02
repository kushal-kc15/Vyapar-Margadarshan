"""
Base settings for vyapar_margadarshan project.
"""
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured
from decouple import config
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSECURE_SECRET_KEY = 'django-insecure-dev-key-change-in-production'


def config_bool(name, default=False):
    """
    Read a boolean env value with a few deployment-friendly aliases.
    Keeps invalid values from crashing imports before settings can override them.
    """
    value = config(name, default=default)
    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()
    if normalized in {'1', 'true', 't', 'yes', 'y', 'on', 'dev', 'development'}:
        return True
    if normalized in {'0', 'false', 'f', 'no', 'n', 'off', 'prod', 'production', 'release'}:
        return False

    raise ImproperlyConfigured(f'{name} must be a boolean-like value, got {value!r}.')


def config_list(name, default=''):
    """Read a comma-separated env value into a cleaned list."""
    value = config(name, default=default)
    return [item.strip() for item in str(value).split(',') if item.strip()]


def database_config_from_url(database_url):
    """Small DATABASE_URL parser to avoid hard-coding SQLite in production."""
    parsed = urlparse(database_url)

    if parsed.scheme in {'sqlite', 'sqlite3'}:
        if parsed.path in {'', '/'}:
            name = BASE_DIR / 'db.sqlite3'
        elif parsed.netloc:
            name = f'//{parsed.netloc}{parsed.path}'
        else:
            name = parsed.path.lstrip('/') if parsed.path.startswith('/') else parsed.path
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': name,
        }

    if parsed.scheme in {'postgres', 'postgresql'}:
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': parsed.path.lstrip('/'),
            'USER': parsed.username or '',
            'PASSWORD': parsed.password or '',
            'HOST': parsed.hostname or '',
            'PORT': parsed.port or '',
        }

    raise ImproperlyConfigured(
        'DATABASE_URL must start with sqlite:/// or postgres:// / postgresql://.'
    )


SECRET_KEY = config('SECRET_KEY', default=INSECURE_SECRET_KEY)

GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID', default='')

DEBUG = config_bool('DEBUG', default=True)

ALLOWED_HOSTS = config_list('ALLOWED_HOSTS', default='localhost,127.0.0.1')

# Application definition
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    
    # Local apps
    'users',
    'expenses',
    'organizations',
    'budgets',
    'analytics',
    'activity_logs',
    'receipts',
    'notifications',
]

JAZZMIN_SETTINGS = {
    'site_title': 'Vyapar Admin',
    'site_header': 'Vyapar Margadarshan',
    'site_brand': 'Vyapar Margadarshan',
    'welcome_sign': 'Website Manager Console',
    'copyright': 'Vyapar Margadarshan',
    'search_model': [],
    'topmenu_links': [
        {'name': 'Dashboard', 'url': 'admin:index', 'permissions': ['auth.view_user']},
        {'name': 'Platform', 'model': 'users.User'},
        {'name': 'Finance', 'model': 'expenses.Expense'},
        {'name': 'System', 'model': 'activity_logs.ActivityLog'},
    ],
    'show_sidebar': True,
    'navigation_expanded': True,
    'hide_apps': [
        'auth',
        'analytics',
        'sessions',
        'token_blacklist',
    ],
    'hide_models': [
        'users.PasswordResetToken',
        'users.TwoFactorOTP',
    ],
    'order_with_respect_to': [
        'users.User',
        'organizations.Organization',
        'organizations.OrganizationMember',
        'organizations.Invitation',
        'expenses.Expense',
        'budgets.Budget',
        'budgets.BudgetAlert',
        'receipts.Receipt',
        'notifications.Notification',
        'activity_logs.ActivityLog',
    ],
    'icons': {
        'users.User': 'fas fa-user',
        'organizations.Organization': 'fas fa-building',
        'organizations.OrganizationMember': 'fas fa-users-cog',
        'organizations.Invitation': 'fas fa-envelope-open-text',
        'expenses.Expense': 'fas fa-receipt',
        'budgets.Budget': 'fas fa-wallet',
        'budgets.BudgetAlert': 'fas fa-exclamation-triangle',
        'receipts.Receipt': 'fas fa-file-invoice',
        'notifications.Notification': 'fas fa-bell',
        'activity_logs.ActivityLog': 'fas fa-history',
    },
    'related_modal_active': False,
    'changeform_format': 'horizontal_tabs',
    'show_ui_builder': False,
}

JAZZMIN_UI_TWEAKS = {
    'theme': 'litera',
    'dark_mode_theme': 'darkly',
    'navbar': 'navbar-dark navbar-olive',
    'brand_colour': 'navbar-olive',
    'accent': 'accent-orange',
    'sidebar': 'sidebar-dark-olive',
    'no_navbar_border': True,
    'navbar_fixed': True,
    'sidebar_fixed': True,
    'actions_sticky_top': True,
    'body_small_text': False,
    'sidebar_nav_small_text': True,
    'sidebar_disable_expand': False,
    'sidebar_nav_child_indent': True,
    'sidebar_nav_compact_style': True,
    'footer_small_text': True,
    'button_classes': {
        'primary': 'btn-success',
        'secondary': 'btn-outline-dark',
        'info': 'btn-info',
        'warning': 'btn-warning',
        'danger': 'btn-danger',
        'success': 'btn-success',
    },
}

# Custom User Model
AUTH_USER_MODEL = 'users.User'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'vyapar_margadarshan.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'libraries': {
                'admin_dashboard': 'activity_logs.templatetags.admin_dashboard',
            },
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'vyapar_margadarshan.wsgi.application'

# Database
DATABASES = {
    'default': database_config_from_url(config('DATABASE_URL', default='sqlite:///db.sqlite3'))
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kathmandu'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'
RECEIPT_MAX_UPLOAD_SIZE_MB = config('RECEIPT_MAX_UPLOAD_SIZE_MB', default=5, cast=int)
RECEIPT_MAX_UPLOAD_SIZE_BYTES = RECEIPT_MAX_UPLOAD_SIZE_MB * 1024 * 1024
RECEIPT_ALLOWED_CONTENT_TYPES = config_list(
    'RECEIPT_ALLOWED_CONTENT_TYPES',
    default='image/jpeg,image/png,image/webp',
)
AI_RECEIPT_SCAN_ENABLED = config_bool('AI_RECEIPT_SCAN_ENABLED', default=True)
GEMINI_API_KEY = config('GEMINI_API_KEY', default='')
GEMINI_RECEIPT_MODEL = config('GEMINI_RECEIPT_MODEL', default='gemini-2.5-flash')
RECEIPT_OCR_USE_QUEUE = config_bool('RECEIPT_OCR_USE_QUEUE', default=False)

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'EXCEPTION_HANDLER': 'vyapar_margadarshan.api_exceptions.api_exception_handler',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_RATES': {
        'auth_register': config('THROTTLE_AUTH_REGISTER', default='5/hour'),
        'auth_login': config('THROTTLE_AUTH_LOGIN', default='5/minute'),
        'auth_google': config('THROTTLE_AUTH_GOOGLE', default='10/minute'),
        'auth_refresh': config('THROTTLE_AUTH_REFRESH', default='20/minute'),
        'auth_resend_verification': config('THROTTLE_AUTH_RESEND_VERIFICATION', default='3/hour'),
        'auth_verify_email': config('THROTTLE_AUTH_VERIFY_EMAIL', default='10/minute'),
        'auth_password_reset': config('THROTTLE_AUTH_PASSWORD_RESET', default='5/hour'),
        'auth_password_reset_confirm': config('THROTTLE_AUTH_PASSWORD_RESET_CONFIRM', default='10/hour'),
        'auth_password_strength': config('THROTTLE_AUTH_PASSWORD_STRENGTH', default='30/minute'),
        'auth_otp_send': config('THROTTLE_AUTH_OTP_SEND', default='5/minute'),
        'auth_otp_verify': config('THROTTLE_AUTH_OTP_VERIFY', default='10/minute'),
        'auth_security_user': config('THROTTLE_AUTH_SECURITY_USER', default='10/minute'),
    },
}

# JWT settings
JWT_REMEMBER_ME_REFRESH_TOKEN_LIFETIME = timedelta(
    minutes=config('JWT_REMEMBER_ME_REFRESH_TOKEN_LIFETIME', default=43200, cast=int)
)

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        minutes=config('JWT_ACCESS_TOKEN_LIFETIME', default=15, cast=int)
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        minutes=config('JWT_REFRESH_TOKEN_LIFETIME', default=10080, cast=int)
    ),
    'ROTATE_REFRESH_TOKENS': config_bool('JWT_ROTATE_REFRESH_TOKENS', default=True),
    'BLACKLIST_AFTER_ROTATION': config_bool('JWT_BLACKLIST_AFTER_ROTATION', default=True),
    'UPDATE_LAST_LOGIN': config_bool('JWT_UPDATE_LAST_LOGIN', default=True),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'SIGNING_KEY': config('JWT_SIGNING_KEY', default=SECRET_KEY),
    'LEEWAY': config('JWT_LEEWAY_SECONDS', default=0, cast=int),
}

# CORS settings
CORS_ALLOWED_ORIGINS = config_list(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174',
)
CORS_ALLOW_CREDENTIALS = config_bool('CORS_ALLOW_CREDENTIALS', default=False)
CORS_ALLOW_HEADERS = list(default_headers) + [
    'x-organization-id',
]

# Email settings
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@vyaparmargadarshan.com')

# Frontend URL (for email links)
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:5173')

# Temporarily disable login-time 2FA challenges while the app is being finalized.
# Existing user 2FA preferences are preserved and can be enforced again by setting this true.
TWO_FACTOR_LOGIN_ENABLED = config_bool('TWO_FACTOR_LOGIN_ENABLED', default=False)

# Celery background jobs
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/1')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = config_bool('CELERY_TASK_ALWAYS_EAGER', default=False)
CELERY_TASK_EAGER_PROPAGATES = config_bool('CELERY_TASK_EAGER_PROPAGATES', default=DEBUG)
OCR_QUEUE_FALLBACK_SYNC = config_bool('OCR_QUEUE_FALLBACK_SYNC', default=DEBUG)
