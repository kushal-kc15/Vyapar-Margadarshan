"""Deterministic spending advice built from approved workspace data."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from budgets.models import Budget
from expenses.models import Expense
from receipts.models import Receipt


ZERO = Decimal('0')
CATEGORY_CONCENTRATION_PERCENT = Decimal('50')
VENDOR_CONCENTRATION_PERCENT = Decimal('40')
MONTHLY_INCREASE_PERCENT = Decimal('20')


def _money(value):
    return f"{Decimal(value or ZERO):.2f}"


def _percentage(part, whole):
    part = Decimal(part or ZERO)
    whole = Decimal(whole or ZERO)
    if whole <= 0:
        return ZERO
    return (part / whole * Decimal('100')).quantize(Decimal('0.1'))


def _expense_scope(organization, user, role):
    queryset = Expense.objects.filter(
        organization=organization,
        status='APPROVED',
    )
    if str(role or '').upper() != 'OWNER':
        queryset = queryset.filter(user=user)
    return queryset


def _advisory(code, severity, title, message, recommendation, evidence):
    return {
        'code': code,
        'severity': severity,
        'title': title,
        'message': message,
        'recommendation': recommendation,
        'evidence': evidence,
        'source': 'rule_based',
    }


def generate_rule_based_advice(organization, user, start_date, end_date, role):
    """Return repeatable advice without calling AI or creating records."""
    base_expenses = _expense_scope(organization, user, role)
    expenses = base_expenses.filter(date__gte=start_date, date__lte=end_date)
    totals = expenses.aggregate(total=Sum('amount'), count=Count('id'))
    approved_total = Decimal(totals['total'] or ZERO)
    approved_count = totals['count'] or 0
    advisories = []

    if approved_count == 0:
        advisories.append(_advisory(
            'NO_APPROVED_EXPENSES',
            'info',
            'No approved expenses',
            'No approved expenses found for this period.',
            'Confirm that expense records and the selected report dates are up to date.',
            {'approved_count': 0},
        ))
    else:
        top_category = expenses.values('category').annotate(
            total=Sum('amount'), count=Count('id'),
        ).order_by('-total', 'category').first()
        if top_category:
            category_share = _percentage(top_category['total'], approved_total)
            if category_share >= CATEGORY_CONCENTRATION_PERCENT:
                advisories.append(_advisory(
                    'CATEGORY_CONCENTRATION',
                    'warning',
                    f"{top_category['category']} spending is concentrated",
                    f"{top_category['category']} represents {category_share}% of approved spending.",
                    'Review this category before approving additional discretionary expenses.',
                    {
                        'category': top_category['category'],
                        'percentage': float(category_share),
                        'amount': _money(top_category['total']),
                    },
                ))

        if approved_count >= 3:
            top_vendor = expenses.exclude(vendor__isnull=True).exclude(vendor='').values('vendor').annotate(
                total=Sum('amount'), count=Count('id'),
            ).order_by('-total', 'vendor').first()
            if top_vendor:
                vendor_share = _percentage(top_vendor['total'], approved_total)
                if vendor_share >= VENDOR_CONCENTRATION_PERCENT:
                    advisories.append(_advisory(
                        'VENDOR_CONCENTRATION',
                        'warning',
                        f"High spending with {top_vendor['vendor']}",
                        f"{top_vendor['vendor']} receives {vendor_share}% of approved spending.",
                        'Review pricing or compare alternative vendors before the next purchase.',
                        {
                            'vendor': top_vendor['vendor'],
                            'percentage': float(vendor_share),
                            'amount': _money(top_vendor['total']),
                            'expense_count': top_vendor['count'],
                        },
                    ))

    # Evaluate active budgets that overlap the selected reporting period. Usage
    # follows the same owner/personal approved-expense scope as analytics.
    budgets = Budget.objects.filter(
        organization=organization,
        is_active=True,
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).order_by('name', 'id')
    for budget in budgets:
        budget_expenses = base_expenses.filter(
            date__gte=budget.start_date,
            date__lte=budget.end_date,
        )
        if budget.category != 'ALL':
            budget_expenses = budget_expenses.filter(category=budget.category)
        spent = Decimal(budget_expenses.aggregate(total=Sum('amount'))['total'] or ZERO)
        percentage_used = _percentage(spent, budget.amount)
        evidence = {
            'budget_id': budget.id,
            'budget_name': budget.name,
            'category': budget.category,
            'percentage_used': float(percentage_used),
            'spent_amount': _money(spent),
            'budget_amount': _money(budget.amount),
        }
        if percentage_used >= 100:
            advisories.append(_advisory(
                'BUDGET_EXCEEDED',
                'danger',
                f"{budget.name} has been exceeded",
                f"This budget has used {percentage_used}% of its configured limit.",
                'Review new spending in this budget and adjust the limit only when justified.',
                evidence,
            ))
        elif percentage_used >= Decimal(budget.alert_threshold):
            advisories.append(_advisory(
                'BUDGET_NEAR_LIMIT',
                'warning',
                f"{budget.name} is near its limit",
                f"This budget has used {percentage_used}% of its configured limit.",
                'Review non-essential spending before approving more expenses in this budget.',
                evidence,
            ))

    period_days = max((end_date - start_date).days + 1, 1)
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=period_days - 1)
    previous_total = Decimal(base_expenses.filter(
        date__gte=previous_start,
        date__lte=previous_end,
    ).aggregate(total=Sum('amount'))['total'] or ZERO)
    if previous_total > 0:
        increase = ((approved_total - previous_total) / previous_total * Decimal('100')).quantize(Decimal('0.1'))
        if increase >= MONTHLY_INCREASE_PERCENT:
            advisories.append(_advisory(
                'MONTHLY_SPEND_INCREASE',
                'warning',
                'Spending increased',
                f"Approved spending increased by {increase}% compared with the previous comparable period.",
                'Review the largest categories and vendors contributing to the increase.',
                {
                    'increase_percentage': float(increase),
                    'current_total': _money(approved_total),
                    'previous_total': _money(previous_total),
                    'previous_start_date': previous_start.isoformat(),
                    'previous_end_date': previous_end.isoformat(),
                },
            ))

    # Receipt compliance: flag when missing-receipt rate is above 20%
    if approved_count >= 5:
        receipt_count = Receipt.objects.filter(
            expense__organization=organization,
            expense__status='APPROVED',
            expense__date__gte=start_date,
            expense__date__lte=end_date,
        ).count()
        missing_receipts = approved_count - receipt_count
        missing_rate = _percentage(missing_receipts, approved_count)
        if missing_rate >= Decimal('20'):
            advisories.append(_advisory(
                'RECEIPT_COMPLIANCE',
                'warning',
                'Receipt compliance needs attention',
                f"{missing_rate}% of approved expenses have no receipt attached.",
                'Remind submitters to attach receipts before requesting approval.',
                {
                    'missing_count': missing_receipts,
                    'total_count': approved_count,
                    'missing_rate': float(missing_rate),
                },
            ))

    # Approval bottleneck: flag when pending expenses are stacking up
    pending_expenses = Expense.objects.filter(
        organization=organization,
        status__in=['SUBMITTED', 'PENDING', 'IN_REVIEW'],
    )
    if str(role or '').upper() != 'OWNER':
        pending_expenses = pending_expenses.filter(user=user)
    pending_count = pending_expenses.count()
    if pending_count >= 5:
        today = timezone.localdate()
        total_days = sum((today - e.date).days for e in pending_expenses.only('date'))
        avg_days = round(total_days / pending_count, 1) if pending_count else 0
        advisories.append(_advisory(
            'APPROVAL_BOTTLENECK',
            'warning' if pending_count < 10 else 'danger',
            'Pending expenses are accumulating',
            f"{pending_count} expenses are waiting for review (avg. {avg_days} days).",
            'Prioritize reviewing the oldest pending expenses to avoid delays.',
            {
                'pending_count': pending_count,
                'average_pending_days': avg_days,
            },
        ))

    severity_order = {'danger': 0, 'warning': 1, 'info': 2, 'success': 3}
    advisories.sort(key=lambda item: (severity_order[item['severity']], item['code'], item['title']))
    return {
        'organization_id': organization.id,
        'scope': 'organization' if str(role or '').upper() == 'OWNER' else 'personal',
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
        },
        'summary': {
            'approved_total': _money(approved_total),
            'approved_count': approved_count,
        },
        'advisories': advisories,
    }
