from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal

from .categories import REAL_EXPENSE_CATEGORY_CHOICES


class Expense(models.Model):
    """
    Expense model for tracking business expenses.
    """
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('PENDING', 'Pending Review'),
        ('IN_REVIEW', 'In Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('RETURNED', 'Returned'),
    ]

    # Expense categories are real expense categories only (NO 'ALL').
    CATEGORY_CHOICES = REAL_EXPENSE_CATEGORY_CHOICES
    
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='expenses',
        null=True,
        blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='expenses'
    )
    title = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    vendor = models.CharField(max_length=255, blank=True, null=True)
    date = models.DateField()
    description = models.TextField(blank=True)

    # Decision metadata (approved/rejected by an owner)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_expenses',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='APPROVED'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'expenses'
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['organization', 'status', 'date'], name='exp_org_stat_dt_idx'),
            models.Index(fields=['user', 'organization', 'status', 'date'], name='exp_user_org_st_dt_idx'),
            models.Index(fields=['organization', 'category', 'status', 'date'], name='exp_org_cat_st_dt_idx'),
            models.Index(fields=['organization', 'vendor'], name='exp_org_vendor_idx'),
        ]
    
    def __str__(self):
        return f"{self.title} - रू {self.amount}"


class ApprovalAuditLog(models.Model):
    """Records every status transition in the expense approval workflow."""
    TRANSITION_CHOICES = [
        ('SUBMITTED', 'Submitted for Review'),
        ('REVIEW_STARTED', 'Review Started'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('RETURNED', 'Returned for Changes'),
        ('RESUBMITTED', 'Resubmitted'),
        ('AUTO_APPROVED', 'Auto-Approved by Rule Engine'),
    ]

    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name='approval_audit_logs'
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='approval_actions'
    )
    transition = models.CharField(max_length=15, choices=TRANSITION_CHOICES)
    from_status = models.CharField(max_length=10, blank=True)
    to_status = models.CharField(max_length=10)
    reason = models.TextField(blank=True)
    rule_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'approval_audit_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['expense', '-created_at'], name='aal_expense_ts_idx'),
        ]

    def __str__(self):
        return f"{self.expense_id} | {self.transition} by {self.actor_id} at {self.created_at}"
