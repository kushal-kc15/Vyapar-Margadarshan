"""
Rule Context Builder.

Prepares the factual context needed by the rule engine for a single expense:
historical baselines, vendor history, duplicate candidates, budget pressure,
receipt status, and statistical outlier detection. Keeps database queries out
of the rule engine itself.
"""
import math
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from budgets.models import Budget
from expenses.models import Expense
from receipts.models import Receipt

STATISTICAL_MINIMUM_COUNT = 8


def _category_baseline(base_queryset, expense, minimum_count):
    baseline = base_queryset.filter(
        category=expense.category,
        date__lt=expense.date,
    ).exclude(id=expense.id).aggregate(avg=Avg('amount'), count=Count('id'))
    if (baseline['count'] or 0) < minimum_count or not baseline['avg']:
        return None
    return baseline


def _vendor_baseline(base_queryset, expense, minimum_count):
    if not expense.vendor:
        return None
    baseline = base_queryset.filter(
        vendor__iexact=expense.vendor,
        date__lt=expense.date,
    ).exclude(id=expense.id).aggregate(avg=Avg('amount'), count=Count('id'))
    if (baseline['count'] or 0) < minimum_count or not baseline['avg']:
        return None
    return baseline


def _duplicate_candidates(base_queryset, expense, window_days):
    start = expense.date - timedelta(days=window_days)
    end = expense.date + timedelta(days=window_days)
    queryset = base_queryset.filter(
        amount=expense.amount,
        category=expense.category,
        date__gte=start,
        date__lte=end,
    ).exclude(id=expense.id)
    if expense.vendor:
        queryset = queryset.filter(vendor__iexact=expense.vendor)
    return list(queryset.order_by('-date', '-created_at')[:5])


def _is_new_vendor(base_queryset, expense):
    if not expense.vendor:
        return False
    return not base_queryset.filter(
        vendor__iexact=expense.vendor,
        date__lt=expense.date,
    ).exclude(id=expense.id).exists()


def _budget_pressure(expense):
    budgets = Budget.objects.filter(
        organization=expense.organization,
        is_active=True,
        start_date__lte=expense.date,
        end_date__gte=expense.date,
    ).filter(Q(category='ALL') | Q(category=expense.category))

    highest_percentage = 0
    for budget in budgets:
        approved_total = Expense.objects.filter(
            organization=expense.organization,
            status='APPROVED',
            date__gte=budget.start_date,
            date__lte=budget.end_date,
        )
        if budget.category != 'ALL':
            approved_total = approved_total.filter(category=budget.category)
        spent = approved_total.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        projected_spend = spent + expense.amount
        percentage = (
            float((projected_spend / budget.amount) * Decimal('100'))
            if budget.amount else 0
        )
        highest_percentage = max(highest_percentage, percentage)
    return round(highest_percentage, 1)


def _category_statistical_baseline(base_queryset, expense):
    """Compute median, IQR, and z-score for the expense's category.

    Returns None if fewer than STATISTICAL_MINIMUM_COUNT historical records
    exist (statistical measures are unreliable with small samples).
    """
    amounts = list(
        base_queryset.filter(
            category=expense.category,
            date__lt=expense.date,
        ).exclude(id=expense.id)
        .values_list('amount', flat=True)
        .order_by('amount')
    )
    n = len(amounts)
    if n < STATISTICAL_MINIMUM_COUNT:
        return None

    amounts_float = [float(a) for a in amounts]
    expense_amount = float(expense.amount)

    # Median
    mid = n // 2
    median = (amounts_float[mid] + amounts_float[mid - 1]) / 2 if n % 2 == 0 else amounts_float[mid]

    # Quartiles (inclusive method)
    def quartile(data, q):
        pos = (len(data) - 1) * q
        lower = int(math.floor(pos))
        upper = int(math.ceil(pos))
        if lower == upper:
            return data[lower]
        return data[lower] * (upper - pos) + data[upper] * (pos - lower)

    q1 = quartile(amounts_float, 0.25)
    q3 = quartile(amounts_float, 0.75)
    iqr = q3 - q1

    # IQR outlier fence
    upper_fence = q3 + 1.5 * iqr
    is_iqr_outlier = expense_amount > upper_fence

    # Z-score
    mean = sum(amounts_float) / n
    variance = sum((x - mean) ** 2 for x in amounts_float) / n
    std_dev = math.sqrt(variance) if variance > 0 else 0
    z_score = (expense_amount - mean) / std_dev if std_dev > 0 else 0

    return {
        'median': round(median, 2),
        'q1': round(q1, 2),
        'q3': round(q3, 2),
        'iqr': round(iqr, 2),
        'upper_fence': round(upper_fence, 2),
        'mean': round(mean, 2),
        'std_dev': round(std_dev, 2),
        'z_score': round(z_score, 2),
        'is_iqr_outlier': is_iqr_outlier,
        'sample_size': n,
    }


def build_context(expense, base_queryset, *, amount_multiplier=Decimal('2.5'),
                  minimum_baseline_count=3, duplicate_window_days=3):
    """Build the full evaluation context for a single expense.

    Returns a dict consumed by rule_engine.evaluate_expense().
    """
    pending_days = max(0, (timezone.localdate() - expense.date).days)

    return {
        'amount_multiplier': Decimal(str(amount_multiplier)),
        'category_stats': _category_baseline(base_queryset, expense, minimum_baseline_count),
        'vendor_stats': _vendor_baseline(base_queryset, expense, minimum_baseline_count),
        'statistical_baseline': _category_statistical_baseline(base_queryset, expense),
        'duplicate_candidates': _duplicate_candidates(base_queryset, expense, duplicate_window_days),
        'is_new_vendor': _is_new_vendor(base_queryset, expense),
        'has_receipt': Receipt.objects.filter(expense_id=expense.id).exists(),
        'budget_percentage': _budget_pressure(expense),
        'pending_days': pending_days,
    }
