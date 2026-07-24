"""Helpers for recording approval audit log entries."""
from .models import ApprovalAuditLog


def record_transition(expense, *, actor, transition, from_status, to_status,
                      reason='', rule_snapshot=None):
    """Create an ApprovalAuditLog entry for a workflow transition."""
    return ApprovalAuditLog.objects.create(
        expense=expense,
        actor=actor,
        transition=transition,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        rule_snapshot=rule_snapshot or {},
    )
