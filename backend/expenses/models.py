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
        default='PENDING'
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
