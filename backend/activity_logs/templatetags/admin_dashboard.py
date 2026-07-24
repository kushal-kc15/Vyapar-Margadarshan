from django import template
from django.urls import NoReverseMatch, reverse

from activity_logs.models import ActivityLog
from budgets.models import Budget
from expenses.models import Expense
from organizations.models import Organization
from receipts.models import Receipt
from users.models import User


register = template.Library()


def admin_change_url(obj):
    try:
        return reverse(
            f'admin:{obj._meta.app_label}_{obj._meta.model_name}_change',
            args=[obj.pk],
        )
    except NoReverseMatch:
        return ''


def admin_changelist_url(model):
    try:
        return reverse(
            f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist'
        )
    except NoReverseMatch:
        return ''


@register.simple_tag
def admin_dashboard_data():
    recent_users = User.objects.order_by('-created_at')[:5]
    recent_organizations = Organization.objects.order_by('-created_at')[:5]
    recent_expenses = (
        Expense.objects.select_related('organization', 'user')
        .order_by('-created_at')[:5]
    )
    recent_activity_logs = (
        ActivityLog.objects.select_related('organization', 'user')
        .order_by('-timestamp')[:5]
    )

    return {
        'summary_cards': [
            {
                'label': 'Total Users',
                'value': User.objects.count(),
                'icon': 'fas fa-user',
                'url': admin_changelist_url(User),
            },
            {
                'label': 'Organizations',
                'value': Organization.objects.count(),
                'icon': 'fas fa-building',
                'url': admin_changelist_url(Organization),
            },
            {
                'label': 'Total Expenses',
                'value': Expense.objects.count(),
                'icon': 'fas fa-receipt',
                'url': admin_changelist_url(Expense),
            },
            {
                'label': 'Pending Expenses',
                'value': Expense.objects.filter(status__in=['SUBMITTED', 'PENDING', 'IN_REVIEW']).count(),
                'icon': 'fas fa-hourglass-half',
                'url': admin_changelist_url(Expense),
            },
            {
                'label': 'Active Budgets',
                'value': Budget.objects.filter(is_active=True).count(),
                'icon': 'fas fa-wallet',
                'url': admin_changelist_url(Budget),
            },
            {
                'label': 'Receipts',
                'value': Receipt.objects.count(),
                'icon': 'fas fa-file-invoice',
                'url': admin_changelist_url(Receipt),
            },
        ],
        'recent_organizations': [
            {
                'name': organization.name,
                'detail': organization.contact_email or organization.industry or 'Organization workspace',
                'created_at': organization.created_at,
                'url': admin_change_url(organization),
            }
            for organization in recent_organizations
        ],
        'recent_users': [
            {
                'name': user.get_full_name() or user.username,
                'detail': user.email or user.username,
                'created_at': user.created_at,
                'url': admin_change_url(user),
            }
            for user in recent_users
        ],
        'recent_expenses': [
            {
                'name': expense.title,
                'detail': f'{expense.organization} · {expense.status}',
                'amount': expense.amount,
                'created_at': expense.created_at,
                'url': admin_change_url(expense),
            }
            for expense in recent_expenses
        ],
        'recent_activity_logs': [
            {
                'name': activity.get_action_type_display(),
                'detail': activity.description,
                'created_at': activity.timestamp,
                'url': admin_change_url(activity),
            }
            for activity in recent_activity_logs
        ],
    }
