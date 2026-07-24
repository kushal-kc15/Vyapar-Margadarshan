"""
Rule-driven approval routing.

Uses the rule engine's risk assessment to determine the approval path
for a submitted expense. Low-risk expenses can be auto-approved,
medium-risk ones go through standard review, and high-risk expenses
require explicit owner attention.
"""
from datetime import timedelta
from decimal import Decimal

from expenses.models import Expense
from .rule_context import build_context
from .rule_engine import evaluate_expense


ROUTING_DECISIONS = {
    'AUTO_APPROVE': 'auto_approve',
    'STANDARD_REVIEW': 'standard_review',
    'PRIORITY_REVIEW': 'priority_review',
}

AUTO_APPROVE_MAX_SCORE = 10
PRIORITY_REVIEW_MIN_SCORE = 50


def route_expense(expense, organization):
    """Determine the approval route for an expense based on rule evaluation.

    Args:
        expense: Expense instance (status should be SUBMITTED).
        organization: Organization the expense belongs to.

    Returns:
        Dict with routing decision, risk assessment, and rationale.
    """
    base_queryset = Expense.objects.filter(
        organization=organization,
        status__in={'APPROVED', 'SUBMITTED', 'PENDING', 'IN_REVIEW'},
        date__gte=expense.date - timedelta(days=180),
        date__lte=expense.date,
    ).select_related('user', 'organization')

    context = build_context(expense, base_queryset)
    result = evaluate_expense(expense, context)

    score = result['risk_score']
    level = result['risk_level']

    if score <= AUTO_APPROVE_MAX_SCORE and level == 'LOW':
        decision = ROUTING_DECISIONS['AUTO_APPROVE']
        rationale = 'Expense is low-risk with no significant flags.'
    elif score >= PRIORITY_REVIEW_MIN_SCORE:
        decision = ROUTING_DECISIONS['PRIORITY_REVIEW']
        rationale = 'Expense has significant risk indicators requiring priority review.'
    else:
        decision = ROUTING_DECISIONS['STANDARD_REVIEW']
        rationale = 'Expense requires standard approval review.'

    return {
        'decision': decision,
        'risk_score': score,
        'risk_level': level,
        'triggered_rules': result['triggered_rules'],
        'rule_count': result['rule_count'],
        'rationale': rationale,
        'review_suggestion': result['review_suggestion'],
    }


def apply_routing(expense, organization, *, allow_auto_approve=True):
    """Route an expense and apply the decision.

    For auto-approve: sets status to APPROVED directly.
    For standard/priority review: keeps status as SUBMITTED (or moves to PENDING).

    Args:
        expense: Expense instance.
        organization: Organization instance.
        allow_auto_approve: If False, never auto-approve (useful for orgs
            that want all expenses reviewed regardless of risk).

    Returns:
        Routing result dict with 'applied' flag indicating if status changed.
    """
    routing = route_expense(expense, organization)
    applied = False

    if routing['decision'] == ROUTING_DECISIONS['AUTO_APPROVE'] and allow_auto_approve:
        from django.utils import timezone
        expense.status = 'APPROVED'
        expense.reviewed_at = timezone.now()
        expense.save(update_fields=['status', 'reviewed_at', 'updated_at'])
        applied = True

    routing['applied'] = applied
    routing['expense_status'] = expense.status
    return routing
