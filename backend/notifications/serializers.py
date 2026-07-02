from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'title', 'message', 'priority',
            'related_object_type', 'related_object_id', 'action_url',
            'metadata',
            'is_read', 'read_at', 'created_at', 'time_ago'
        ]
        read_only_fields = ['id', 'created_at', 'time_ago']
    
    def get_time_ago(self, obj):
        """Calculate human-readable time difference"""
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff < timedelta(minutes=1):
            return 'Just now'
        elif diff < timedelta(hours=1):
            minutes = int(diff.total_seconds() / 60)
            return f'{minutes}m ago'
        elif diff < timedelta(days=1):
            hours = int(diff.total_seconds() / 3600)
            return f'{hours}h ago'
        elif diff < timedelta(days=7):
            days = diff.days
            return f'{days}d ago'
        elif diff < timedelta(days=30):
            weeks = diff.days // 7
            return f'{weeks}w ago'
        else:
            return obj.created_at.strftime('%b %d, %Y')
