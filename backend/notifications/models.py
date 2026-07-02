from django.db import models
from django.conf import settings
from organizations.models import Organization


class Notification(models.Model):
    """
    In-app notification model for user alerts and updates.
    """
    TYPE_CHOICES = [
        ('EXPENSE_APPROVED', 'Expense Approved'),
        ('EXPENSE_REJECTED', 'Expense Rejected'),
        ('EXPENSE_PENDING', 'Expense Pending Approval'),
        ('BUDGET_ALERT', 'Budget Alert'),
        ('BUDGET_EXCEEDED', 'Budget Exceeded'),
        ('UNUSUAL_EXPENSE', 'Unusual Expense Submitted'),
        ('INVITATION_RECEIVED', 'Invitation Received'),
        ('MEMBER_JOINED', 'New Member Joined'),
        ('ROLE_CHANGED', 'Role Changed'),
        ('SYSTEM', 'System Notification'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True
    )
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    
    # Optional link to related object
    related_object_type = models.CharField(max_length=50, blank=True, null=True)
    related_object_id = models.IntegerField(blank=True, null=True)
    action_url = models.CharField(max_length=500, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['notification_type']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"
