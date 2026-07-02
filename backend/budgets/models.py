from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from calendar import monthrange
from datetime import timedelta
from django.utils import timezone

from expenses.categories import BUDGET_CATEGORY_CHOICES


def derive_budget_date_range(period, start_date=None):
    """Return a deterministic inclusive range for a budget period."""
    if start_date is None:
        today = timezone.localdate()
        if period == 'DAILY':
            start_date = today
        elif period == 'WEEKLY':
            start_date = today - timedelta(days=today.weekday())
        elif period == 'YEARLY':
            start_date = today.replace(month=1, day=1)
        else:
            start_date = today.replace(day=1)

    if period == 'DAILY':
        end_date = start_date
    elif period == 'WEEKLY':
        end_date = start_date + timedelta(days=6)
    elif period == 'YEARLY':
        try:
            next_period = start_date.replace(year=start_date.year + 1)
        except ValueError:
            next_period = start_date.replace(year=start_date.year + 1, day=28)
        end_date = next_period - timedelta(days=1)
    else:
        next_month = 1 if start_date.month == 12 else start_date.month + 1
        next_year = start_date.year + 1 if start_date.month == 12 else start_date.year
        next_day = min(start_date.day, monthrange(next_year, next_month)[1])
        end_date = start_date.replace(
            year=next_year,
            month=next_month,
            day=next_day,
        ) - timedelta(days=1)
    return start_date, end_date


class Budget(models.Model):
    """
    Budget model for tracking spending limits by category and period.
    """
    PERIOD_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
        ('YEARLY', 'Yearly'),
    ]

    CATEGORY_CHOICES = BUDGET_CATEGORY_CHOICES
    
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='budgets'
    )
    name = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='ALL')
    alert_threshold = models.IntegerField(
        default=80,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text='Percentage at which to trigger alert (1-100)'
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_budgets'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'budgets'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'is_active', 'category'], name='bud_org_act_cat_idx'),
            models.Index(fields=['organization', 'is_active', 'start_date', 'end_date'], name='bud_org_act_dates_idx'),
        ]
    
    def __str__(self):
        return f"{self.name} - रू {self.amount} ({self.period})"


    def save(self, *args, **kwargs):
        if not self.start_date:
            self.start_date, derived_end = derive_budget_date_range(self.period)
            self.end_date = self.end_date or derived_end
        elif not self.end_date:
            _, self.end_date = derive_budget_date_range(self.period, self.start_date)
        super().save(*args, **kwargs)


class BudgetAlert(models.Model):
    """
    Alert model for budget threshold notifications.
    """
    ALERT_TYPE_CHOICES = [
        ('THRESHOLD', 'Threshold Reached'),
        ('EXCEEDED', 'Budget Exceeded'),
    ]
    
    budget = models.ForeignKey(
        Budget,
        on_delete=models.CASCADE,
        related_name='alerts'
    )
    alert_type = models.CharField(max_length=10, choices=ALERT_TYPE_CHOICES)
    percentage = models.IntegerField()
    amount_spent = models.DecimalField(max_digits=10, decimal_places=2)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'budget_alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['budget', 'alert_type'], name='bud_alert_type_idx'),
            models.Index(fields=['is_read', '-created_at'], name='bud_alert_read_dt_idx'),
        ]
    
    def __str__(self):
        return f"{self.budget.name} - {self.alert_type}"
