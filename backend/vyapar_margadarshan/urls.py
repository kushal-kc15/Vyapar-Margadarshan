"""
URL configuration for vyapar_margadarshan project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from .health import health_check, root

urlpatterns = [
    path('', root, name='api-root'),
    
    path('admin/', admin.site.urls),

    # Health check endpoint (used by uptime/load balancer checks)
    path('health/', health_check, name='health-check'),

    # Authentication endpoints
    path('api/auth/', include('users.urls')),
    
    # Expenses endpoints
    path('api/', include('expenses.urls')),
    
    # Organizations endpoints
    path('api/', include('organizations.urls')),
    
    # Budgets endpoints
    path('api/', include('budgets.urls')),
    
    # Analytics endpoints
    path('api/analytics/', include('analytics.urls')),
    
    # Activity logs endpoints
    path('api/activity-logs/', include('activity_logs.urls')),
    
    # Receipts endpoints
    path('api/receipts/', include('receipts.urls')),
    
    # Notifications endpoints
    path('api/notifications/', include('notifications.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
