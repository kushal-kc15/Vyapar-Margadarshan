import csv
from datetime import date, timedelta
from decimal import Decimal

from django.http import HttpResponse
from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from budgets.models import Budget
from .ai_insights import AIInsightError, generate_ai_insight
from .rule_advisory import generate_rule_based_advice
from .pdf_report import build_expense_report_pdf
from expenses.models import Expense
from organizations.context import get_active_membership

PERIOD_TRUNCATORS = {
    'daily': TruncDay,
    'weekly': TruncWeek,
    'monthly': TruncMonth,
}

PERIOD_TYPES = {'day', 'week', 'month', 'year'}
ANOMALY_STATUSES = {'APPROVED', 'PENDING'}


def money(value):
    return float(value or Decimal('0'))


def percent(numerator, denominator, precision=2):
    denominator = Decimal(str(denominator or 0))
    numerator = Decimal(str(numerator or 0))
    if denominator <= 0:
        return 0
    return round(float((numerator / denominator) * Decimal('100')), precision)


def decimal_string(value):
    return f"{Decimal(str(value or 0)):.2f}"


def safe_csv_text(value):
    text = '' if value is None else str(value)
    if text.startswith(('=', '+', '-', '@')):
        return f"'{text}"
    return text


def category_label(category):
    return dict(Expense.CATEGORY_CHOICES).get(category, category or '')


def report_period_label(period_start, period):
    if not period_start:
        return ''
    if hasattr(period_start, 'date'):
        period_start = period_start.date()
    return period_start.strftime('%b %Y' if period == 'monthly' else '%b %d')


def parse_date_param(request, name):
    value = request.query_params.get(name)
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({name: 'Use YYYY-MM-DD format.'}) from exc


def get_member_or_error(request):
    member = get_active_membership(request.user, request)
    if not member:
        raise ValidationError({'organization': 'Select or join a workspace first.'})
    return member


def scoped_expenses(request):
    """
    Approved spend analytics only. Owners see organization spend; staff see their own approved spend.
    """
    member = get_member_or_error(request)
    queryset = Expense.objects.filter(organization=member.organization, status='APPROVED')
    if member.role != 'OWNER':
        queryset = queryset.filter(user=request.user)
    return queryset, member


def apply_date_filters(queryset, request):
    start_date = parse_date_param(request, 'start_date')
    end_date = parse_date_param(request, 'end_date')
    if start_date and end_date and start_date > end_date:
        raise ValidationError({'date_range': 'start_date cannot be after end_date.'})
    if start_date:
        queryset = queryset.filter(date__gte=start_date)
    if end_date:
        queryset = queryset.filter(date__lte=end_date)
    return queryset, start_date, end_date


def apply_report_filters(queryset, request):
    queryset, start_date, end_date = apply_date_filters(queryset, request)
    category = request.query_params.get('category')
    vendor = (request.query_params.get('vendor') or '').strip()

    if category:
        valid_categories = {value for value, _label in Expense.CATEGORY_CHOICES}
        category = category.upper()
        if category not in valid_categories:
            raise ValidationError({'category': 'Use a valid expense category.'})
        queryset = queryset.filter(category=category)

    if vendor:
        queryset = queryset.filter(vendor__icontains=vendor)

    return queryset, start_date, end_date, category, vendor


def apply_category_vendor_filters(queryset, category='', vendor=''):
    if category:
        queryset = queryset.filter(category=category)
    if vendor:
        queryset = queryset.filter(vendor__icontains=vendor)
    return queryset


def parse_limit(request, default=10, maximum=50):
    raw_limit = request.query_params.get('limit', default)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise ValidationError({'limit': 'Use a positive integer.'}) from exc
    if limit < 1:
        raise ValidationError({'limit': 'Use a positive integer.'})
    return min(limit, maximum)


def parse_positive_int(request, name, default, maximum):
    raw_value = request.query_params.get(name, default)
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({name: 'Use a positive integer.'}) from exc
    if value < 1:
        raise ValidationError({name: 'Use a positive integer.'})
    return min(value, maximum)


def parse_period(request):
    period = request.query_params.get('period', 'daily')
    if period not in PERIOD_TRUNCATORS:
        raise ValidationError({'period': 'Use daily, weekly, or monthly.'})
    return period


def summarize_queryset(queryset):
    summary = queryset.aggregate(total=Sum('amount'), count=Count('id'), average=Avg('amount'))
    return {
        'total': money(summary['total']),
        'count': summary['count'] or 0,
        'average': money(summary['average']),
    }


def scoped_anomaly_expenses(request):
    """
    Anomaly detection includes pending and approved spend so owners can review suspicious submissions early.
    """
    member = get_member_or_error(request)
    queryset = Expense.objects.filter(
        organization=member.organization,
        status__in=ANOMALY_STATUSES,
    ).select_related('user', 'organization')
    if member.role != 'OWNER':
        queryset = queryset.filter(user=request.user)
    return queryset, member


def current_and_previous_period(period_type):
    today = timezone.now().date()
    if period_type == 'day':
        current_start = today
        current_end = today
        previous_start = today - timedelta(days=1)
        previous_end = previous_start
    elif period_type == 'week':
        current_start = today - timedelta(days=today.weekday())
        current_end = today
        previous_start = current_start - timedelta(days=7)
        previous_end = current_start - timedelta(days=1)
    elif period_type == 'year':
        current_start = today.replace(month=1, day=1)
        current_end = today
        previous_start = current_start.replace(year=current_start.year - 1)
        previous_end = current_start - timedelta(days=1)
    else:
        current_start = today.replace(day=1)
        current_end = today
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end.replace(day=1)
    return current_start, current_end, previous_start, previous_end


def budget_bounds(budget):
    today = timezone.now().date()
    if budget.start_date and budget.end_date:
        return budget.start_date, budget.end_date
    if budget.period == 'DAILY':
        return today, today
    if budget.period == 'WEEKLY':
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    if budget.period == 'YEARLY':
        return today.replace(month=1, day=1), today.replace(month=12, day=31)
    start = today.replace(day=1)
    if today.month == 12:
        end = today.replace(day=31)
    else:
        end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    return start, end


def ai_insight_period_bounds(period):
    today = timezone.now().date()
    current_start = today.replace(day=1)
    if period == 'this_month':
        return current_start, today
    if period == 'last_month':
        end = current_start - timedelta(days=1)
        return end.replace(day=1), end
    if period == 'last_3_months':
        month = current_start
        for _ in range(2):
            month = (month - timedelta(days=1)).replace(day=1)
        return month, today
    raise ValidationError({'period': 'Use this_month, last_month, or last_3_months.'})


def period_change(current_total, previous_total):
    current_total = Decimal(str(current_total or 0))
    previous_total = Decimal(str(previous_total or 0))
    if previous_total > 0:
        return round(float(((current_total - previous_total) / previous_total) * Decimal('100')), 2)
    return 0 if current_total == 0 else 100


def severity_from_score(score):
    if score >= 80:
        return 'HIGH'
    if score >= 50:
        return 'MEDIUM'
    return 'LOW'


def build_expense_snapshot(expense):
    return {
        'expense_id': expense.id,
        'id': expense.id,
        'title': expense.title,
        'description': expense.description or '',
        'amount': money(expense.amount),
        'category': expense.category,
        'vendor': expense.vendor or '',
        'date': expense.date,
        'status': expense.status,
        'user_id': expense.user_id,
        'user_name': expense.user.get_full_name() or expense.user.username,
    }


def top_category_rows(queryset, limit=5):
    return [
        {
            'category': row['category'],
            'total': money(row['total']),
            'count': row['count'],
        }
        for row in queryset.values('category').annotate(
            total=Sum('amount'),
            count=Count('id'),
        ).order_by('-total')[:limit]
    ]


def top_vendor_rows(queryset, limit=5):
    return [
        {
            'vendor': row['vendor'],
            'total': money(row['total']),
            'count': row['count'],
        }
        for row in queryset.exclude(vendor__isnull=True).exclude(vendor='').values('vendor').annotate(
            total=Sum('amount'),
            count=Count('id'),
        ).order_by('-total')[:limit]
    ]


def build_ai_insight_snapshot(request):
    base_expenses, member = scoped_expenses(request)
    period = (
        request.data.get('period', 'this_month')
        if request.method == 'POST'
        else request.query_params.get('period', 'this_month')
    )
    start_date, end_date = ai_insight_period_bounds(period)
    expenses = base_expenses.filter(date__gte=start_date, date__lte=end_date)
    summary = summarize_queryset(expenses)
    highest_expenses = [
        {
            'title': expense.title,
            'amount': money(expense.amount),
            'category': expense.category,
            'vendor': expense.vendor or '',
            'date': expense.date,
        }
        for expense in expenses.order_by('-amount', '-date')[:5]
    ]

    return {
        'organization_id': member.organization_id,
        'scope': 'organization' if member.role == 'OWNER' else 'personal',
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'total_approved_amount': summary['total'],
        'expense_count': summary['count'],
        'top_categories': top_category_rows(expenses, limit=5),
        'top_vendors': top_vendor_rows(expenses, limit=5),
        'highest_expenses': highest_expenses,
    }


def fallback_ai_insight(snapshot):
    top_category = snapshot['top_categories'][0] if snapshot['top_categories'] else None
    top_vendor = snapshot['top_vendors'][0] if snapshot['top_vendors'] else None
    summary = (
        f"Approved spend for this period is {snapshot['total_approved_amount']} across "
        f"{snapshot['expense_count']} expenses."
    )
    insights = []
    if top_category:
        insights.append(f"{top_category['category']} is the largest category at {top_category['total']}.")
    if top_vendor:
        insights.append(f"{top_vendor['vendor']} is the top vendor at {top_vendor['total']}.")
    if snapshot['highest_expenses']:
        highest = snapshot['highest_expenses'][0]
        insights.append(f"The highest expense is {highest['title']} at {highest['amount']}.")

    warnings = []
    if top_category and snapshot['total_approved_amount']:
        category_share = (top_category['total'] / snapshot['total_approved_amount']) * 100
        if category_share >= 60:
            warnings.append(f"{top_category['category']} represents {round(category_share)}% of approved spend.")

    recommendations = [
        'Review the highest category before approving new discretionary spending.',
        'Compare top vendors for consolidation or negotiated pricing opportunities.',
    ]

    return {
        'summary': summary,
        'insights': insights[:4],
        'warnings': warnings[:3],
        'recommendations': recommendations[:3],
        'provider': 'fallback',
        'model': '',
    }


def category_baseline(base_queryset, expense, minimum_count):
    baseline = base_queryset.filter(
        category=expense.category,
        date__lt=expense.date,
    ).exclude(id=expense.id).aggregate(avg=Avg('amount'), count=Count('id'))
    if (baseline['count'] or 0) < minimum_count or not baseline['avg']:
        return None
    return baseline


def vendor_baseline(base_queryset, expense, minimum_count):
    if not expense.vendor:
        return None
    baseline = base_queryset.filter(
        vendor__iexact=expense.vendor,
        date__lt=expense.date,
    ).exclude(id=expense.id).aggregate(avg=Avg('amount'), count=Count('id'))
    if (baseline['count'] or 0) < minimum_count or not baseline['avg']:
        return None
    return baseline


def duplicate_candidates(base_queryset, expense, window_days):
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


def is_new_vendor(base_queryset, expense):
    if not expense.vendor:
        return False
    return not base_queryset.filter(
        vendor__iexact=expense.vendor,
        date__lt=expense.date,
    ).exclude(id=expense.id).exists()


def detect_expense_anomalies(expense, base_queryset, *, amount_multiplier, minimum_baseline_count, duplicate_window_days):
    reasons = []
    score = 0

    category_stats = category_baseline(base_queryset, expense, minimum_baseline_count)
    if category_stats:
        average = Decimal(str(category_stats['avg']))
        ratio = expense.amount / average if average > 0 else Decimal('0')
        if ratio >= amount_multiplier:
            score += min(45, int(float(ratio) * 10))
            reasons.append({
                'code': 'HIGH_CATEGORY_AMOUNT',
                'message': 'Amount is unusually high for this category.',
                'baseline_average': money(average),
                'baseline_count': category_stats['count'],
                'ratio': round(float(ratio), 2),
            })

    vendor_stats = vendor_baseline(base_queryset, expense, minimum_baseline_count)
    if vendor_stats:
        average = Decimal(str(vendor_stats['avg']))
        ratio = expense.amount / average if average > 0 else Decimal('0')
        if ratio >= amount_multiplier:
            score += min(35, int(float(ratio) * 8))
            reasons.append({
                'code': 'HIGH_VENDOR_AMOUNT',
                'message': 'Amount is unusually high for this vendor.',
                'baseline_average': money(average),
                'baseline_count': vendor_stats['count'],
                'ratio': round(float(ratio), 2),
            })

    duplicates = duplicate_candidates(base_queryset, expense, duplicate_window_days)
    if duplicates:
        score += 35
        reasons.append({
            'code': 'DUPLICATE_CANDIDATE',
            'message': 'Similar expense exists near the same date.',
            'matching_expense_ids': [candidate.id for candidate in duplicates],
        })

    if is_new_vendor(base_queryset, expense):
        score += 15
        reasons.append({
            'code': 'NEW_VENDOR',
            'message': 'Vendor has no prior spend history in this scope.',
        })

    if expense.date.weekday() >= 5:
        score += 10
        reasons.append({
            'code': 'WEEKEND_EXPENSE',
            'message': 'Expense date falls on a weekend.',
        })

    if not reasons:
        return None

    score = min(score, 100)
    return {
        **build_expense_snapshot(expense),
        'score': score,
        'severity': severity_from_score(score),
        'reasons': reasons,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def spending_trends(request):
    period = parse_period(request)

    expenses, member = scoped_expenses(request)
    expenses, start_date, end_date = apply_date_filters(expenses, request)
    trunc_func = PERIOD_TRUNCATORS[period]

    rows = expenses.annotate(period_bucket=trunc_func('date')).values('period_bucket').annotate(
        total=Sum('amount'),
        count=Count('id'),
    ).order_by('period_bucket')

    trends = [
        {
            'period': row['period_bucket'],
            'period_start': row['period_bucket'],
            'total': money(row['total']),
            'count': row['count'],
        }
        for row in rows
    ]

    return Response({
        'organization_id': member.organization_id,
        'scope': 'organization' if member.role == 'OWNER' else 'personal',
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'trends': trends,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_csv(request):
    period = parse_period(request)

    expenses, member = scoped_expenses(request)
    expenses, start_date, end_date, category, vendor = apply_report_filters(expenses, request)
    summary = expenses.aggregate(total=Sum('amount'), count=Count('id'))
    total_amount = summary['total'] or Decimal('0')
    total_count = summary['count'] or 0

    category_rows = list(
        expenses.values('category').annotate(
            total=Sum('amount'),
            count=Count('id'),
        ).order_by('-total', 'category')
    )
    vendor_rows = list(
        expenses.exclude(vendor__isnull=True).exclude(vendor='').values('vendor').annotate(
            total=Sum('amount'),
            count=Count('id'),
        ).order_by('-total', 'vendor')
    )

    trunc_func = PERIOD_TRUNCATORS[period]
    trend_rows = list(
        expenses.annotate(period_bucket=trunc_func('date')).values('period_bucket').annotate(
            total=Sum('amount'),
            count=Count('id'),
        ).order_by('period_bucket')
    )

    top_category = category_rows[0] if category_rows else None
    top_vendor = vendor_rows[0] if vendor_rows else None
    generated_at = timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S %Z')
    date_range = (
        f'{start_date.isoformat() if start_date else "Beginning"} to '
        f'{end_date.isoformat() if end_date else "Present"}'
    )

    filename_start = start_date.isoformat() if start_date else 'all'
    filename_end = end_date.isoformat() if end_date else 'all'
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response.write('\ufeff')
    response['Content-Disposition'] = (
        f'attachment; filename="approved-expense-report_{filename_start}_{filename_end}.csv"'
    )
    writer = csv.writer(response)

    writer.writerow(['Vyapar Margadarshan Approved Expense Report'])
    writer.writerow([])
    writer.writerow(['Report Summary'])
    writer.writerow(['Organization', safe_csv_text(member.organization.name)])
    writer.writerow(['Date range', date_range])
    writer.writerow(['Generated at', generated_at])
    writer.writerow(['Currency', request.user.default_currency])
    writer.writerow(['Data scope', 'Approved expenses only'])
    writer.writerow(['View scope', 'Organization' if member.role == 'OWNER' else 'Personal'])
    writer.writerow(['Category filter', safe_csv_text(category_label(category)) if category else 'All categories'])
    writer.writerow(['Vendor filter', safe_csv_text(vendor) if vendor else 'All vendors'])
    writer.writerow(['Approved amount', decimal_string(total_amount)])
    writer.writerow(['Total approved expenses', total_count])
    writer.writerow([
        'Top category',
        safe_csv_text(category_label(top_category['category'])) if top_category else 'Unavailable',
    ])
    writer.writerow([
        'Top category amount',
        decimal_string(top_category['total']) if top_category else '0.00',
    ])
    writer.writerow([
        'Top vendor',
        safe_csv_text(top_vendor['vendor']) if top_vendor else 'Unavailable',
    ])
    writer.writerow([
        'Top vendor amount',
        decimal_string(top_vendor['total']) if top_vendor else '0.00',
    ])

    writer.writerow([])
    writer.writerow(['Category Breakdown'])
    writer.writerow(['Category', 'Entries', 'Total spend', 'Share %'])
    for row in category_rows:
        writer.writerow([
            safe_csv_text(category_label(row['category'])),
            row['count'],
            decimal_string(row['total']),
            decimal_string(percent(row['total'], total_amount)),
        ])

    writer.writerow([])
    writer.writerow(['Vendor Summary'])
    writer.writerow(['Vendor', 'Entries', 'Total spend'])
    for row in vendor_rows:
        writer.writerow([
            safe_csv_text(row['vendor']),
            row['count'],
            decimal_string(row['total']),
        ])

    writer.writerow([])
    writer.writerow(['Spending Trend'])
    writer.writerow(['Period', 'Period start', 'Total spend', 'Count'])
    for row in trend_rows:
        period_start = row['period_bucket']
        if hasattr(period_start, 'date'):
            period_start = period_start.date()
        writer.writerow([
            report_period_label(period_start, period),
            period_start.isoformat() if period_start else '',
            decimal_string(row['total']),
            row['count'],
        ])

    writer.writerow([])
    writer.writerow(['Approved Expenses Included'])
    writer.writerow(['Date', 'Title', 'Description', 'Category', 'Vendor', 'Submitted by', 'Amount'])
    for expense in expenses.select_related('user').order_by('-date', '-created_at', '-id'):
        writer.writerow([
            expense.date.isoformat(),
            safe_csv_text(expense.title),
            safe_csv_text(expense.description),
            safe_csv_text(category_label(expense.category)),
            safe_csv_text(expense.vendor),
            safe_csv_text(expense.user.get_full_name() or expense.user.username),
            decimal_string(expense.amount),
        ])

    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_pdf(request):
    parse_period(request)  # Keep validation consistent with CSV/report requests.
    expenses, member = scoped_expenses(request)
    expenses, start_date, end_date, category, vendor = apply_report_filters(expenses, request)
    pdf_bytes = build_expense_report_pdf(
        member=member,
        user=request.user,
        expenses=expenses,
        start_date=start_date,
        end_date=end_date,
        category=category,
        vendor=vendor,
        category_label=category_label,
    )
    filename_start = start_date.isoformat() if start_date else 'all'
    filename_end = end_date.isoformat() if end_date else 'all'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="Vyapar_Margadarshan_Report_{filename_start}_to_{filename_end}.pdf"'
    )
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def category_breakdown(request):
    expenses, member = scoped_expenses(request)
    expenses, start_date, end_date, _category, _vendor = apply_report_filters(expenses, request)
    total_amount = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')

    rows = expenses.values('category').annotate(
        total=Sum('amount'),
        count=Count('id'),
    ).order_by('-total')

    breakdown = [
        {
            'category': row['category'],
            'total': money(row['total']),
            'count': row['count'],
            'percentage': percent(row['total'], total_amount),
        }
        for row in rows
    ]

    return Response({
        'organization_id': member.organization_id,
        'scope': 'organization' if member.role == 'OWNER' else 'personal',
        'start_date': start_date,
        'end_date': end_date,
        'breakdown': breakdown,
        'total_amount': money(total_amount),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def period_comparison(request):
    period_type = request.query_params.get('period_type', 'month')
    if period_type not in PERIOD_TYPES:
        raise ValidationError({'period_type': 'Use day, week, month, or year.'})

    base_expenses, member = scoped_expenses(request)
    current_start, current_end, previous_start, previous_end = current_and_previous_period(period_type)
    current_summary = summarize_queryset(base_expenses.filter(date__gte=current_start, date__lte=current_end))
    previous_summary = summarize_queryset(base_expenses.filter(date__gte=previous_start, date__lte=previous_end))

    previous_total = Decimal(str(previous_summary['total']))
    current_total = Decimal(str(current_summary['total']))
    if previous_total > 0:
        change_percentage = round(float(((current_total - previous_total) / previous_total) * Decimal('100')), 2)
    else:
        change_percentage = 0 if current_total == 0 else 100

    return Response({
        'organization_id': member.organization_id,
        'scope': 'organization' if member.role == 'OWNER' else 'personal',
        'period_type': period_type,
        'current_period': {
            'start': current_start,
            'end': current_end,
            **current_summary,
        },
        'previous_period': {
            'start': previous_start,
            'end': previous_end,
            **previous_summary,
        },
        'change_percentage': change_percentage,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vendor_summary(request):
    expenses, member = scoped_expenses(request)
    expenses, start_date, end_date, _category, _vendor = apply_report_filters(expenses, request)
    limit = parse_limit(request)

    rows = expenses.exclude(vendor__isnull=True).exclude(vendor='').values('vendor').annotate(
        total=Sum('amount'),
        count=Count('id'),
    ).order_by('-total')[:limit]

    vendors = [
        {
            'vendor': row['vendor'],
            'total': money(row['total']),
            'count': row['count'],
        }
        for row in rows
    ]

    return Response({
        'organization_id': member.organization_id,
        'scope': 'organization' if member.role == 'OWNER' else 'personal',
        'start_date': start_date,
        'end_date': end_date,
        'vendors': vendors,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def budget_burn_rate(request):
    member = get_member_or_error(request)
    today = timezone.now().date()
    budgets = Budget.objects.filter(
        organization=member.organization,
        is_active=True,
    ).order_by('category', 'name')

    rows = []
    for budget in budgets:
        start, end = budget_bounds(budget)
        expense_filter = {
            'organization': member.organization,
            'status': 'APPROVED',
            'date__gte': start,
            'date__lte': end,
        }
        if budget.category != 'ALL':
            expense_filter['category'] = budget.category
        spent = Expense.objects.filter(**expense_filter).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        days_total = max((end - start).days + 1, 1)
        elapsed_end = min(max(today, start), end)
        days_elapsed = max((elapsed_end - start).days + 1, 1)
        daily_burn = spent / Decimal(days_elapsed)
        projected_spend = daily_burn * Decimal(days_total)

        rows.append({
            'budget_id': budget.id,
            'name': budget.name,
            'category': budget.category,
            'period': budget.period,
            'start_date': start,
            'end_date': end,
            'budget_amount': money(budget.amount),
            'spent_amount': money(spent),
            'remaining_amount': money(budget.amount - spent),
            'percentage_used': percent(spent, budget.amount, precision=1),
            'days_elapsed': days_elapsed,
            'days_total': days_total,
            'elapsed_percentage': round((days_elapsed / days_total) * 100, 1),
            'daily_burn_rate': money(daily_burn),
            'projected_spend': money(projected_spend),
            'projected_percentage_used': percent(projected_spend, budget.amount, precision=1),
            'is_over_budget': spent > budget.amount,
            'is_projected_over_budget': projected_spend > budget.amount,
        })

    return Response({
        'organization_id': member.organization_id,
        'budgets': rows,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def overview(request):
    expenses, member = scoped_expenses(request)
    expenses, start_date, end_date, _category, _vendor = apply_report_filters(expenses, request)
    summary = summarize_queryset(expenses)
    category_count = expenses.values('category').distinct().count()
    vendor_count = expenses.exclude(vendor__isnull=True).exclude(vendor='').values('vendor').distinct().count()

    return Response({
        'organization_id': member.organization_id,
        'scope': 'organization' if member.role == 'OWNER' else 'personal',
        'start_date': start_date,
        'end_date': end_date,
        'total_spent': summary['total'],
        'transaction_count': summary['count'],
        'category_count': category_count,
        'vendor_count': vendor_count,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def report_detail(request):
    period = parse_period(request)
    base_expenses, member = scoped_expenses(request)
    expenses, start_date, end_date, category, vendor = apply_report_filters(base_expenses, request)

    summary = summarize_queryset(expenses)
    total_amount = Decimal(str(summary['total']))

    category_rows = list(
        expenses.values('category').annotate(
            total=Sum('amount'),
            count=Count('id'),
        ).order_by('-total', 'category')
    )
    categories = [
        {
            'category': row['category'],
            'total': money(row['total']),
            'count': row['count'],
            'percentage': percent(row['total'], total_amount),
        }
        for row in category_rows
    ]

    vendor_rows = list(
        expenses.exclude(vendor__isnull=True).exclude(vendor='').values('vendor').annotate(
            total=Sum('amount'),
            count=Count('id'),
        ).order_by('-total', 'vendor')[:10]
    )
    vendors = [
        {
            'vendor': row['vendor'],
            'total': money(row['total']),
            'count': row['count'],
            'percentage': percent(row['total'], total_amount),
        }
        for row in vendor_rows
    ]

    trunc_func = PERIOD_TRUNCATORS[period]
    trends = [
        {
            'period': row['period_bucket'],
            'period_start': row['period_bucket'],
            'total': money(row['total']),
            'count': row['count'],
        }
        for row in expenses.annotate(period_bucket=trunc_func('date')).values('period_bucket').annotate(
            total=Sum('amount'),
            count=Count('id'),
        ).order_by('period_bucket')
    ]

    if start_date and end_date:
        range_days = max((end_date - start_date).days + 1, 1)
        current_start, current_end = start_date, end_date
        previous_end = start_date - timedelta(days=1)
        previous_start = previous_end - timedelta(days=range_days - 1)
        period_type = 'selected_range'
    else:
        period_type = 'year' if period == 'monthly' else 'month'
        current_start, current_end, previous_start, previous_end = current_and_previous_period(period_type)

    comparison_base = apply_category_vendor_filters(base_expenses, category, vendor)
    comparison = {
        'period_type': period_type,
        'current_period': {
            'start': current_start,
            'end': current_end,
            **summarize_queryset(comparison_base.filter(date__gte=current_start, date__lte=current_end)),
        },
        'previous_period': {
            'start': previous_start,
            'end': previous_end,
            **summarize_queryset(comparison_base.filter(date__gte=previous_start, date__lte=previous_end)),
        },
    }
    comparison['change_percentage'] = period_change(
        comparison['current_period']['total'],
        comparison['previous_period']['total'],
    )

    expense_rows = [
        build_expense_snapshot(expense)
        for expense in expenses.select_related('user').order_by('-date', '-created_at', '-id')[:100]
    ]

    return Response({
        'organization_id': member.organization_id,
        'scope': 'organization' if member.role == 'OWNER' else 'personal',
        'filters': {
            'start_date': start_date,
            'end_date': end_date,
            'category': category or '',
            'vendor': vendor,
            'period': period,
        },
        'summary': summary,
        'top_category': categories[0] if categories else None,
        'top_vendor': vendors[0] if vendors else None,
        'trends': trends,
        'categories': categories,
        'vendors': vendors,
        'comparison': comparison,
        'expenses': expense_rows,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rule_based_advice(request):
    """Return deterministic advice for the selected approved-spend period."""
    member = get_member_or_error(request)
    start_date = parse_date_param(request, 'start_date')
    end_date = parse_date_param(request, 'end_date')
    today = timezone.localdate()
    start_date = start_date or today.replace(day=1)
    end_date = end_date or today
    if start_date > end_date:
        raise ValidationError({'date_range': 'start_date cannot be after end_date.'})

    return Response(generate_rule_based_advice(
        organization=member.organization,
        user=request.user,
        start_date=start_date,
        end_date=end_date,
        role=member.role,
    ))


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def ai_insights(request):
    snapshot = build_ai_insight_snapshot(request)
    if snapshot['expense_count'] == 0:
        return Response({
            'organization_id': snapshot['organization_id'],
            'scope': snapshot['scope'],
            'period': snapshot['period'],
            'start_date': snapshot['start_date'],
            'end_date': snapshot['end_date'],
            'enough_data': False,
            'generated_by_ai': False,
            'summary': '',
            'insights': [],
            'warnings': [],
            'recommendations': [],
            'provider': 'none',
            'model': '',
            'snapshot_metrics': {
                'total_approved_amount': 0,
                'expense_count': 0,
            },
        })

    generated_by_ai = True
    try:
        insight = generate_ai_insight(snapshot)
    except AIInsightError:
        generated_by_ai = False
        insight = fallback_ai_insight(snapshot)

    return Response({
        'organization_id': snapshot['organization_id'],
        'scope': snapshot['scope'],
        'period': snapshot['period'],
        'start_date': snapshot['start_date'],
        'end_date': snapshot['end_date'],
        'enough_data': True,
        'generated_by_ai': generated_by_ai,
        'summary': insight['summary'],
        'insights': insight['insights'],
        'warnings': insight['warnings'],
        'recommendations': insight['recommendations'],
        'provider': insight['provider'],
        'model': insight['model'],
        'snapshot_metrics': {
            'total_approved_amount': snapshot['total_approved_amount'],
            'expense_count': snapshot['expense_count'],
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def anomalies(request):
    expenses, member = scoped_anomaly_expenses(request)
    lookback_days = parse_positive_int(request, 'lookback_days', default=180, maximum=730)
    limit = parse_limit(request, default=20, maximum=100)
    minimum_baseline_count = parse_positive_int(request, 'minimum_baseline_count', default=3, maximum=50)
    duplicate_window_days = parse_positive_int(request, 'duplicate_window_days', default=3, maximum=30)

    raw_multiplier = request.query_params.get('amount_multiplier', 2.5)
    try:
        amount_multiplier = Decimal(str(raw_multiplier))
    except Exception as exc:
        raise ValidationError({'amount_multiplier': 'Use a positive number.'}) from exc
    if amount_multiplier <= 1:
        raise ValidationError({'amount_multiplier': 'Use a number greater than 1.'})

    today = timezone.now().date()
    cutoff = today - timedelta(days=lookback_days)
    base_queryset = expenses.filter(date__gte=cutoff, date__lte=today)
    candidate_queryset, start_date, end_date = apply_date_filters(base_queryset, request)
    candidates = candidate_queryset.order_by('-date', '-created_at')[:limit * 3]

    flagged = []
    for expense in candidates:
        anomaly = detect_expense_anomalies(
            expense,
            base_queryset,
            amount_multiplier=amount_multiplier,
            minimum_baseline_count=minimum_baseline_count,
            duplicate_window_days=duplicate_window_days,
        )
        if anomaly:
            flagged.append(anomaly)

    flagged.sort(key=lambda item: (item['score'], item['date'], item['expense_id']), reverse=True)

    return Response({
        'organization_id': member.organization_id,
        'scope': 'organization' if member.role == 'OWNER' else 'personal',
        'lookback_days': lookback_days,
        'start_date': start_date,
        'end_date': end_date,
        'rules': [
            'HIGH_CATEGORY_AMOUNT',
            'HIGH_VENDOR_AMOUNT',
            'DUPLICATE_CANDIDATE',
            'NEW_VENDOR',
            'WEEKEND_EXPENSE',
        ],
        'total_flagged': len(flagged),
        'anomalies': flagged[:limit],
    })
