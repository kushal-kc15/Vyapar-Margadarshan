"""
Rule Engine for expense anomaly detection.

Evaluates a single expense against the rule knowledge base using a prepared
context dict. Returns structured results with triggered rules, score
contributions, evidence, and recommendations.

Rules are read from the database (BusinessRule model) when available,
falling back to the static EXPENSE_REVIEW_RULES dict otherwise.
"""
import logging
from decimal import Decimal

from .rule_knowledge_base import EXPENSE_REVIEW_RULES

_logger = logging.getLogger(__name__)


def _load_rules():
    """Load rules from DB if populated, else fall back to static dict."""
    try:
        from .models import BusinessRule
        db_rules = BusinessRule.objects.all()
        if db_rules.exists():
            return {
                rule.code: {
                    'name': rule.name,
                    'category': rule.category,
                    'description': rule.description,
                    'score': rule.score,
                    'severity': rule.severity,
                    'recommendation': rule.recommendation,
                    'enabled': rule.enabled,
                    'version': rule.version,
                }
                for rule in db_rules
            }
    except Exception:
        _logger.debug('BusinessRule table not available, using static rules.')
    return EXPENSE_REVIEW_RULES


def risk_level_from_score(score):
    if score >= 66:
        return 'HIGH'
    if score >= 31:
        return 'MEDIUM'
    return 'LOW'


def _apply_rule(code, reasons, rules, evidence=None):
    rule = rules.get(code)
    if not rule:
        return 0
    if not rule.get('enabled', True):
        return 0
    item = {
        'code': code,
        'name': rule['name'],
        'category': rule['category'],
        'message': rule['description'],
        'score': rule['score'],
        'severity': rule['severity'],
        'recommendation': rule['recommendation'],
    }
    if evidence:
        item.update(evidence)
    reasons.append(item)
    return rule['score']


def review_suggestion(reason_codes):
    codes = set(reason_codes)
    if {'MISSING_RECEIPT', 'DUPLICATE_CANDIDATE'} & codes:
        return 'Verify the receipt and confirm the expense details before approval.'
    if {'BUDGET_EXCEEDED', 'BUDGET_PRESSURE'} & codes:
        return 'Compare this expense with the available category budget before approval.'
    if {'HIGH_CATEGORY_AMOUNT', 'HIGH_VENDOR_AMOUNT', 'HIGH_AMOUNT_CRITICAL',
            'HIGH_AMOUNT_ELEVATED', 'HIGH_AMOUNT_ROUTINE'} & codes:
        return 'Confirm the amount and business purpose before approval.'
    if {'MISSING_VENDOR', 'WEAK_DESCRIPTION'} & codes:
        return 'Request complete vendor and business-purpose details before approval.'
    return 'Review the expense details and supporting record before approval.'


def evaluate_expense(expense, context):
    """Evaluate a single expense against all enabled rules.

    Args:
        expense: Expense model instance.
        context: Dict prepared by rule_context.build_context() containing
                 precomputed baselines, duplicate info, budget pressure, etc.

    Returns:
        Dict with risk_score, risk_level, triggered_rules, recommendations,
        and review_suggestion.
    """
    rules = _load_rules()
    reasons = []
    score = 0

    # --- Spending pattern rules ---
    category_stats = context.get('category_stats')
    if category_stats:
        average = Decimal(str(category_stats['avg']))
        ratio = expense.amount / average if average > 0 else Decimal('0')
        if ratio >= context.get('amount_multiplier', Decimal('2.5')):
            score += _apply_rule('HIGH_CATEGORY_AMOUNT', reasons, rules, {
                'baseline_average': float(average),
                'baseline_count': category_stats['count'],
                'ratio': round(float(ratio), 2),
            })

    vendor_stats = context.get('vendor_stats')
    if vendor_stats:
        average = Decimal(str(vendor_stats['avg']))
        ratio = expense.amount / average if average > 0 else Decimal('0')
        if ratio >= context.get('amount_multiplier', Decimal('2.5')):
            score += _apply_rule('HIGH_VENDOR_AMOUNT', reasons, rules, {
                'baseline_average': float(average),
                'baseline_count': vendor_stats['count'],
                'ratio': round(float(ratio), 2),
            })

    # Monthly spending spike (moving average comparison)
    monthly_spike = context.get('monthly_spike')
    if monthly_spike and monthly_spike['spike_ratio'] >= 2.0:
        score += _apply_rule('MONTHLY_SPIKE', reasons, rules, {
            'current_month_total': monthly_spike['current_month_total'],
            'monthly_average': monthly_spike['monthly_average'],
            'spike_ratio': monthly_spike['spike_ratio'],
        })

    # Statistical outlier detection (IQR + z-score)
    stat_baseline = context.get('statistical_baseline')
    if stat_baseline and (stat_baseline['is_iqr_outlier'] or stat_baseline['z_score'] > 2):
        score += _apply_rule('CATEGORY_OUTLIER', reasons, rules, {
            'z_score': stat_baseline['z_score'],
            'median': stat_baseline['median'],
            'upper_fence': stat_baseline['upper_fence'],
            'sample_size': stat_baseline['sample_size'],
        })

    # Absolute amount thresholds (only when no category baseline exists)
    if not category_stats:
        thresholds = [
            ('HIGH_AMOUNT_CRITICAL', Decimal('25000')),
            ('HIGH_AMOUNT_ELEVATED', Decimal('10000')),
            ('HIGH_AMOUNT_ROUTINE', Decimal('5000')),
        ]
        for code, threshold in thresholds:
            if expense.amount >= threshold:
                score += _apply_rule(code, reasons, rules, {'amount': float(expense.amount)})
                break

    # --- Duplicate detection ---
    duplicates = context.get('duplicate_candidates')
    if duplicates:
        score += _apply_rule('DUPLICATE_CANDIDATE', reasons, rules, {
            'matching_expense_ids': [d.id for d in duplicates],
        })

    # --- Vendor rules ---
    vendor_raw = str(expense.vendor or '').strip()
    if not vendor_raw or vendor_raw.lower() in {'unknown', 'n/a', 'na'}:
        score += _apply_rule('MISSING_VENDOR', reasons, rules)
    elif context.get('is_new_vendor'):
        score += _apply_rule('NEW_VENDOR', reasons, rules)

    # --- Compliance rules ---
    if not context.get('has_receipt'):
        score += _apply_rule('MISSING_RECEIPT', reasons, rules)

    if len(str(expense.description or '').strip()) < 15:
        score += _apply_rule('WEAK_DESCRIPTION', reasons, rules)

    # --- Budget rules ---
    budget_percentage = context.get('budget_percentage', 0)
    if budget_percentage >= 100:
        score += _apply_rule('BUDGET_EXCEEDED', reasons, rules, {
            'percentage': budget_percentage,
        })
    elif budget_percentage >= 80:
        score += _apply_rule('BUDGET_PRESSURE', reasons, rules, {
            'percentage': budget_percentage,
        })

    # --- Approval workflow rules ---
    pending_days = context.get('pending_days', 0)
    if pending_days > 7:
        score += _apply_rule('OLD_PENDING_EXPENSE', reasons, rules, {
            'pending_days': pending_days,
        })

    score = min(score, 100)
    level = risk_level_from_score(score)
    reason_codes = [r['code'] for r in reasons]

    return {
        'risk_score': score,
        'risk_level': level,
        'triggered_rules': reasons,
        'rule_count': len(reasons),
        'recommendations': [r['recommendation'] for r in reasons],
        'review_suggestion': review_suggestion(reason_codes),
    }
