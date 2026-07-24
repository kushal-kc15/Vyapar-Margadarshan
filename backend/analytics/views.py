import csv
import logging
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
from .ai_insights import generate_ai_insight
from .rule_advisory import generate_rule_based_advice
from .rule_context import build_context
from .rule_engine import evaluate_expense
from .rule_knowledge_base import EXPENSE_REVIEW_RULES, RULE_CATEGORIES
from .pdf_report import build_expense_report_pdf
from expenses.models import Expense
from receipts.models import Receipt
from organizations.context import get_active_membership

logger = logging.getLogger(__name__)

PERIOD_TRUNCATORS = {
    'daily': TruncDay,
    'weekly': TruncWeek,
    'monthly': TruncMonth,
}

PERIOD_TYPES = {'day', 'week', 'month', 'year'}
ANOMALY_STATUSES = {'APPROVED', 'PENDING'}
ACTIONABLE_REVIEW_STATUSES = {'PENDING'}


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
    today = timezone.localdate()
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
    today = timezone.localdate()
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
    today = timezone.localdate()
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
            'category': category_label(row['category']),
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
    category_text = f" The highest spending category is {top_category['category']}." if top_category else ''
    vendor_text = f" The highest spending vendor is {top_vendor['vendor']}." if top_vendor else ''
    summary = (
        f"This period includes {snapshot['expense_count']} approved expenses with total "
        f"spending of NPR {snapshot['total_approved_amount']:,.2f}.{category_text}{vendor_text}"
    )
    insights = []
    if top_category:
        insights.append(f"Most approved spending is concentrated in {top_category['category']}.")
    if top_vendor:
        insights.append(f"{top_vendor['vendor']} has the highest approved vendor total for this period.")
    if snapshot['highest_expenses']:
        highest = snapshot['highest_expenses'][0]
        insights.append(f"The highest expense is {highest['title']} at {highest['amount']}.")

    warnings = []
    if top_category and snapshot['total_approved_amount']:
        category_share = (top_category['total'] / snapshot['total_approved_amount']) * 100
        if category_share >= 60:
            warnings.append(f"{top_category['category']} represents {round(category_share)}% of approved spend.")

    recommendations = [
        'Review high-value expenses before the end of the month.',
        'Compare category-wise spending with the allocated budget.',
    ]

    return {
        'summary': summary,
        'insights': insights[:4],
        'warnings': warnings[:3],
        'recommendations': recommendations[:3],
        'provider': 'fallback',
        'model': '',
    }


def detect_expense_anomalies(expense, base_queryset, *, amount_multiplier, minimum_baseline_count, duplicate_window_days):
    """Evaluate a single expense using the rule engine.

    This is a thin adapter that builds context, runs the engine, and merges
    the result with an expense snapshot for the API response.
    """
    context = build_context(
        expense,
        base_queryset,
        amount_multiplier=amount_multiplier,
        minimum_baseline_count=minimum_baseline_count,
        duplicate_window_days=duplicate_window_days,
    )
    result = evaluate_expense(expense, context)

    # Map triggered_rules back to the legacy 'reasons' format for API compat
    reasons = []
    for rule in result['triggered_rules']:
        reason = {'code': rule['code'], 'message': rule['message']}
        for key in ('baseline_average', 'baseline_count', 'ratio',
                    'matching_expense_ids', 'percentage', 'pending_days', 'amount'):
            if key in rule:
                reason[key] = rule[key]
        reasons.append(reason)

    risk_level = result['risk_level']
    return {
        **build_expense_snapshot(expense),
        'score': result['risk_score'],
        'risk_score': result['risk_score'],
        'severity': risk_level.upper(),
        'risk_level': risk_level.title(),
        'reasons': reasons,
        'triggered_rules': result['triggered_rules'],
        'review_reasons': [r['message'] for r in reasons],
        'review_suggestion': result['review_suggestion'],
        'recommendations': result['recommendations'],
        'rule_count': result['rule_count'],
        'source': 'rules',
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
    today = timezone.localdate()
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
            'summary': 'No approved spending data is available for the selected period.',
            'insights': [],
            'observations': [],
            'warnings': [],
            'recommendations': [],
            'suggestions': [],
            'provider': 'none',
            'source': 'none',
            'model': '',
            'snapshot_metrics': {
                'total_approved_amount': 0,
                'expense_count': 0,
            },
        })

    generated_by_ai = True
    try:
        insight = generate_ai_insight(snapshot)
    except Exception:
        logger.exception('Spending summary provider failed; using database fallback')
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
        'observations': insight['insights'],
        'warnings': insight['warnings'],
        'recommendations': insight['recommendations'],
        'suggestions': insight['recommendations'],
        'provider': insight['provider'],
        'source': insight['provider'],
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

    today = timezone.localdate()
    cutoff = today - timedelta(days=lookback_days)
    base_queryset = expenses.filter(date__gte=cutoff, date__lte=today)
    candidate_queryset, start_date, end_date = apply_date_filters(
        base_queryset.filter(status__in=ACTIONABLE_REVIEW_STATUSES),
        request,
    )
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
        'rules': [code for code, r in EXPENSE_REVIEW_RULES.items() if r.get('enabled')],
        'total_flagged': len(flagged),
        'anomalies': flagged[:limit],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rules(request):
    from .models import BusinessRule

    category_filter = request.query_params.get('category')
    severity_filter = request.query_params.get('severity')

    # Prefer DB-managed rules; fall back to static knowledge base
    db_rules = BusinessRule.objects.all()
    if db_rules.exists():
        queryset = db_rules
        if category_filter:
            queryset = queryset.filter(category=category_filter.upper())
        if severity_filter:
            queryset = queryset.filter(severity=severity_filter.upper())
        rule_list = [
            {
                'code': r.code,
                'name': r.name,
                'category': r.category,
                'category_label': RULE_CATEGORIES.get(r.category, r.category),
                'description': r.description,
                'score': r.score,
                'severity': r.severity,
                'recommendation': r.recommendation,
                'enabled': r.enabled,
                'version': r.version,
            }
            for r in queryset
        ]
    else:
        rule_list = []
        for code, rule in EXPENSE_REVIEW_RULES.items():
            if category_filter and rule['category'] != category_filter.upper():
                continue
            if severity_filter and rule['severity'] != severity_filter.upper():
                continue
            rule_list.append({
                'code': code,
                'name': rule['name'],
                'category': rule['category'],
                'category_label': RULE_CATEGORIES.get(rule['category'], rule['category']),
                'description': rule['description'],
                'score': rule['score'],
                'severity': rule['severity'],
                'recommendation': rule['recommendation'],
                'enabled': rule.get('enabled', True),
                'version': rule.get('version', '1.0'),
            })

    return Response({
        'total': len(rule_list),
        'categories': RULE_CATEGORIES,
        'rules': rule_list,
    })


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def rule_update(request, code):
    from .models import BusinessRule
    from organizations.context import get_active_membership

    member = get_active_membership(request.user, request)
    if not member or member.role != 'OWNER':
        return Response({'error': 'Only owners can update rules.'}, status=403)

    try:
        rule = BusinessRule.objects.get(code=code)
    except BusinessRule.DoesNotExist:
        return Response({'error': 'Rule not found.'}, status=404)

    if 'enabled' in request.data:
        rule.enabled = bool(request.data['enabled'])
    if 'score' in request.data:
        score_val = int(request.data['score'])
        if 1 <= score_val <= 50:
            rule.score = score_val
    if 'severity' in request.data:
        if request.data['severity'] in ('LOW', 'MEDIUM', 'HIGH'):
            rule.severity = request.data['severity']
    rule.save()

    return Response({
        'code': rule.code,
        'name': rule.name,
        'enabled': rule.enabled,
        'score': rule.score,
        'severity': rule.severity,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def routing_preview(request, expense_id):
    """Preview the approval routing decision for a specific expense."""
    from .approval_routing import route_expense

    member = get_member_or_error(request)
    if member.role != 'OWNER':
        return Response({'error': 'Only owners can view routing decisions.'}, status=403)

    try:
        expense = Expense.objects.get(pk=expense_id, organization=member.organization)
    except Expense.DoesNotExist:
        return Response({'error': 'Expense not found.'}, status=404)

    routing = route_expense(expense, member.organization)
    return Response({
        'expense_id': expense.id,
        'expense_title': expense.title,
        'decision': routing['decision'],
        'risk_score': routing['risk_score'],
        'risk_level': routing['risk_level'],
        'rule_count': routing['rule_count'],
        'rationale': routing['rationale'],
        'review_suggestion': routing['review_suggestion'],
        'triggered_rules': [
            {'code': r['code'], 'name': r['name'], 'score': r['score'], 'severity': r['severity']}
            for r in routing['triggered_rules']
        ],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rule_metrics(request):
    """Rule performance metrics: trigger frequency, outcome rates, accuracy."""
    from collections import defaultdict
    from expenses.models import ApprovalAuditLog

    member = get_member_or_error(request)
    if member.role != 'OWNER':
        return Response({'error': 'Only owners can view rule metrics.'}, status=403)

    logs = ApprovalAuditLog.objects.filter(
        expense__organization=member.organization,
        transition__in=['APPROVED', 'REJECTED', 'AUTO_APPROVED'],
    ).exclude(rule_snapshot={})

    rule_stats = defaultdict(lambda: {'triggers': 0, 'approved': 0, 'rejected': 0, 'auto_approved': 0})
    total_decisions = 0

    for log in logs:
        snapshot = log.rule_snapshot or {}
        triggered = snapshot.get('triggered_rules', [])
        transition = log.transition
        total_decisions += 1

        for rule in triggered:
            code = rule.get('code', '')
            if not code:
                continue
            rule_stats[code]['triggers'] += 1
            if transition == 'APPROVED':
                rule_stats[code]['approved'] += 1
            elif transition == 'REJECTED':
                rule_stats[code]['rejected'] += 1
            elif transition == 'AUTO_APPROVED':
                rule_stats[code]['auto_approved'] += 1

    metrics = []
    for code, stats in sorted(rule_stats.items(), key=lambda x: x[1]['triggers'], reverse=True):
        total = stats['triggers']
        rejection_rate = round(stats['rejected'] / total * 100, 1) if total > 0 else 0
        metrics.append({
            'code': code,
            'trigger_count': total,
            'approved_count': stats['approved'],
            'rejected_count': stats['rejected'],
            'auto_approved_count': stats['auto_approved'],
            'rejection_rate': rejection_rate,
        })

    auto_approved_count = logs.filter(transition='AUTO_APPROVED').count()

    return Response({
        'total_decisions': total_decisions,
        'auto_approved_count': auto_approved_count,
        'auto_approval_rate': round(auto_approved_count / total_decisions * 100, 1) if total_decisions > 0 else 0,
        'rule_metrics': metrics,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ml_anomalies(request):
    """Detect anomalies using Isolation Forest ML model."""
    from .ml_anomaly import detect_ml_anomalies

    member = get_member_or_error(request)
    if member.role != 'OWNER':
        return Response({'error': 'Only owners can view ML anomalies.'}, status=403)

    lookback = int(request.query_params.get('lookback_days', 180))
    top_n = int(request.query_params.get('limit', 10))

    results = detect_ml_anomalies(
        member.organization,
        lookback_days=min(lookback, 365),
        top_n=min(top_n, 50),
    )

    if results is None:
        return Response({
            'anomalies': [],
            'model_trained': False,
            'message': 'Insufficient data for ML analysis (minimum 30 approved expenses required).',
        })

    return Response({
        'anomalies': results,
        'model_trained': True,
        'count': len(results),
    })
