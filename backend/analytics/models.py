from django.db import models


class BusinessRule(models.Model):
    SEVERITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
    ]
    CATEGORY_CHOICES = [
        ('SPENDING_PATTERN', 'Spending Pattern'),
        ('FINANCIAL_RISK', 'Financial Risk'),
        ('DUPLICATE', 'Duplicate Detection'),
        ('COMPLIANCE', 'Compliance'),
        ('VENDOR', 'Vendor Risk'),
        ('BUDGET', 'Budget'),
        ('APPROVAL', 'Approval Workflow'),
    ]

    code = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    description = models.TextField()
    score = models.PositiveSmallIntegerField(default=10)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    recommendation = models.TextField()
    threshold = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)
    version = models.CharField(max_length=20, default='1.0')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'code']
        verbose_name = 'Business Rule'
        verbose_name_plural = 'Business Rules'

    def __str__(self):
        return f'{self.code} — {self.name}'
