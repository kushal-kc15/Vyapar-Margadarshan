"""
Utility functions for creating notifications.
"""
import logging

from .models import Notification

logger = logging.getLogger(__name__)


def create_notification(
    user,
    notification_type,
    title,
    message,
    organization=None,
    priority='MEDIUM',
    related_object_type=None,
    related_object_id=None,
    action_url=None,
    metadata=None,
):
    """
    Create an in-app notification for a user.
    """
    return Notification.objects.create(
        user=user,
        organization=organization,
        notification_type=notification_type,
        title=title,
        message=message,
        priority=priority,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        action_url=action_url,
        metadata=metadata or {},
    )


def notify_expense_approved(expense, approved_by):
    """Notify a submitter when their expense is approved."""
    notification = create_notification(
        user=expense.user,
        notification_type='EXPENSE_APPROVED',
        title='Expense Approved',
        message=(
            f'Your expense "{expense.title}" (NPR {expense.amount}) has been '
            f'approved by {approved_by.get_full_name() or approved_by.username}.'
        ),
        organization=expense.organization,
        priority='MEDIUM',
        related_object_type='expense',
        related_object_id=expense.id,
        action_url='/expenses',
    )

    from expenses.emails import send_expense_approval_email
    try:
        send_expense_approval_email(expense, approved_by)
    except Exception:
        logger.exception('Failed to send approval email', extra={'expense_id': expense.id})

    return notification


def notify_expense_rejected(expense, rejected_by, reason=''):
    """Notify a submitter when their expense is rejected."""
    message = (
        f'Your expense "{expense.title}" (NPR {expense.amount}) has been '
        f'rejected by {rejected_by.get_full_name() or rejected_by.username}.'
    )
    if reason:
        message += f' Reason: {reason}'

    notification = create_notification(
        user=expense.user,
        notification_type='EXPENSE_REJECTED',
        title='Expense Rejected',
        message=message,
        organization=expense.organization,
        priority='HIGH',
        related_object_type='expense',
        related_object_id=expense.id,
        action_url='/expenses',
    )

    from expenses.emails import send_expense_rejection_email
    try:
        send_expense_rejection_email(expense, rejected_by, reason)
    except Exception:
        logger.exception('Failed to send rejection email', extra={'expense_id': expense.id})

    return notification


def notify_pending_approval(managers, expense):
    """Notify organization managers about a pending expense approval."""
    notifications = []
    submitter = expense.user.get_full_name() or expense.user.username

    for manager in managers:
        notif = create_notification(
            user=manager.user,
            notification_type='EXPENSE_PENDING',
            title='New Expense Pending',
            message=f'{submitter} submitted "{expense.title}" (NPR {expense.amount}) for approval.',
            organization=expense.organization,
            priority='MEDIUM',
            related_object_type='expense',
            related_object_id=expense.id,
            action_url='/approvals',
        )
        notifications.append(notif)

    return notifications


def notify_budget_alert(user, budget, current_spending, percentage):
    """Notify a user when a budget threshold is reached."""
    return create_notification(
        user=user,
        notification_type='BUDGET_ALERT',
        title='Budget Alert',
        message=(
            f'Your {budget.category} budget has reached {percentage:.1f}% '
            f'(NPR {current_spending} of NPR {budget.amount}).'
        ),
        organization=budget.organization,
        priority='HIGH',
        related_object_type='budget',
        related_object_id=budget.id,
        action_url='/budgets',
    )


def notify_budget_exceeded(user, budget, current_spending, percentage):
    """Notify a user when a budget is exceeded."""
    over_amount = float(current_spending) - float(budget.amount)
    return create_notification(
        user=user,
        notification_type='BUDGET_EXCEEDED',
        title='Budget Exceeded',
        message=(
            f'Your {budget.category} budget has been exceeded by '
            f'NPR {over_amount:.2f} ({percentage:.1f}% used).'
        ),
        organization=budget.organization,
        priority='URGENT',
        related_object_type='budget',
        related_object_id=budget.id,
        action_url='/budgets',
    )


def notify_member_joined(managers, new_member):
    """Notify managers when a new member joins an organization."""
    notifications = []
    member_name = new_member.user.get_full_name() or new_member.user.username

    for manager in managers:
        notif = create_notification(
            user=manager.user,
            notification_type='MEMBER_JOINED',
            title='New Team Member',
            message=f'{member_name} has joined your organization as {new_member.role}.',
            organization=new_member.organization,
            priority='LOW',
            action_url='/team',
        )
        notifications.append(notif)

    return notifications
