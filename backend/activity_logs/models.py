from django.db import models
from django.conf import settings
from organizations.models import Organization


class ActivityLog(models.Model):
    ACTION_TYPES = [
        ('EXPENSE_CREATED', 'Expense Created'),
        ('EXPENSE_UPDATED', 'Expense Updated'),
        ('EXPENSE_DELETED', 'Expense Deleted'),
        ('EXPENSE_SUBMITTED', 'Expense Submitted'),
        ('EXPENSE_APPROVED', 'Expense Approved'),
        ('EXPENSE_REJECTED', 'Expense Rejected'),
        ('EXPENSE_RETURNED', 'Expense Returned'),
        ('EXPENSE_REVIEW_STARTED', 'Expense Review Started'),
        ('BUDGET_CREATED', 'Budget Created'),
        ('BUDGET_UPDATED', 'Budget Updated'),
        ('BUDGET_DELETED', 'Budget Deleted'),
        ('MEMBER_INVITED', 'Member Invited'),
        ('MEMBER_JOINED', 'Member Joined'),
        ('ROLE_CHANGED', 'Role Changed'),
        ('USER_LOGIN', 'User Login'),
        ('USER_LOGOUT', 'User Logout'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='activity_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activity_logs')
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['organization', '-timestamp']),
            models.Index(fields=['organization', 'action_type', '-timestamp'], name='act_org_action_ts_idx'),
            models.Index(fields=['organization', 'user', '-timestamp'], name='act_org_user_ts_idx'),
            models.Index(fields=['action_type']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.action_type} - {self.timestamp}"
