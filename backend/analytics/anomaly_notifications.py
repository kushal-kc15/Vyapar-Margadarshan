"""Failure-tolerant owner notifications for unusual staff expenses."""
import logging
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from expenses.models import Expense
from notifications.models import Notification
from notifications.utils import create_notification
from organizations.models import OrganizationMember


logger = logging.getLogger(__name__)
NOTIFICATION_SCORE_THRESHOLD = 50


def notify_owners_if_expense_is_unusual(expense):
    """Evaluate one new staff expense and notify owners at medium/high severity.

    Detection failures are deliberately non-blocking because recording the
    expense is more important than the advisory side effect.
    """
    try:
        is_staff_submission = OrganizationMember.objects.filter(
            organization=expense.organization,
            user=expense.user,
            role='STAFF',
        ).exists()
        if not is_staff_submission:
            return None

        # Import at call time so the existing endpoint and notification path
        # share the exact same scoring implementation without a dependency
        # cycle during Django app loading.
        from analytics.views import detect_expense_anomalies

        today = timezone.localdate()
        base_queryset = Expense.objects.filter(
            organization=expense.organization,
            status__in={'APPROVED', 'PENDING'},
            date__gte=today - timedelta(days=180),
            date__lte=today,
        ).select_related('user', 'organization')
        anomaly = detect_expense_anomalies(
            expense,
            base_queryset,
            amount_multiplier=Decimal('2.5'),
            minimum_baseline_count=3,
            duplicate_window_days=3,
        )
        if not anomaly or anomaly['score'] < NOTIFICATION_SCORE_THRESHOLD:
            return anomaly

        reason_codes = [reason['code'] for reason in anomaly['reasons']]
        submitter = expense.user.get_full_name() or expense.user.username
        owners = OrganizationMember.objects.filter(
            organization=expense.organization,
            role='OWNER',
        ).select_related('user')

        for owner in owners:
            duplicate = Notification.objects.filter(
                user=owner.user,
                organization=expense.organization,
                notification_type='UNUSUAL_EXPENSE',
                related_object_type='expense',
                related_object_id=expense.id,
            ).exists()
            if duplicate:
                continue
            create_notification(
                user=owner.user,
                organization=expense.organization,
                notification_type='UNUSUAL_EXPENSE',
                title='Unusual expense submitted',
                message=(
                    f'An expense submitted by {submitter} has an anomaly score of '
                    f"{anomaly['score']}. Please review it before approval."
                ),
                priority='HIGH' if anomaly['severity'] == 'HIGH' else 'MEDIUM',
                related_object_type='expense',
                related_object_id=expense.id,
                action_url='/approvals',
                metadata={
                    'expense_id': expense.id,
                    'anomaly_score': anomaly['score'],
                    'severity': anomaly['severity'],
                    'reasons': reason_codes,
                },
            )
        return anomaly
    except Exception:
        logger.exception(
            'Unusual expense notification check failed',
            extra={
                'expense_id': getattr(expense, 'id', None),
                'organization_id': getattr(expense, 'organization_id', None),
            },
        )
        return None
