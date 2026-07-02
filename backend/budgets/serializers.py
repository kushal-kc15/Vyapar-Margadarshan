from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from organizations.context import get_active_membership
from .models import Budget, BudgetAlert, derive_budget_date_range


OVERLAP_MESSAGE = 'An active budget for this category already exists in the selected date range.'


class BudgetSerializer(serializers.ModelSerializer):
    spent_amount = serializers.SerializerMethodField()
    percentage_used = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()

    class Meta:
        model = Budget
        fields = [
            'id', 'organization', 'name', 'amount', 'period', 'category',
            'alert_threshold', 'start_date', 'end_date', 'is_active',
            'created_by', 'created_at', 'updated_at',
            'spent_amount', 'percentage_used', 'remaining_amount',
        ]
        read_only_fields = ['id', 'organization', 'created_by', 'created_at', 'updated_at']

    @staticmethod
    def ensure_effective_dates(budget):
        """Expose a safe range for legacy rows that predate deterministic dates."""
        if budget.start_date and budget.end_date:
            return budget.start_date, budget.end_date

        if budget.start_date:
            start_date = budget.start_date
            _, derived_end = derive_budget_date_range(budget.period, start_date)
            end_date = budget.end_date or derived_end
        else:
            start_date, derived_end = derive_budget_date_range(budget.period)
            end_date = budget.end_date or derived_end

        budget.start_date = start_date
        budget.end_date = end_date
        return start_date, end_date

    def to_representation(self, instance):
        self.ensure_effective_dates(instance)
        return super().to_representation(instance)

    @classmethod
    def precompute_spent_amounts(cls, budgets):
        """Bulk-compute approved spending for each saved budget range."""
        from expenses.models import Expense

        groups = {}
        for budget in budgets:
            cls.ensure_effective_dates(budget)
            category = None if budget.category == 'ALL' else budget.category
            key = (budget.organization_id, budget.start_date, budget.end_date, category)
            groups.setdefault(key, []).append(budget)

        for (organization_id, start_date, end_date, category), grouped in groups.items():
            expenses = Expense.objects.filter(
                organization_id=organization_id,
                status='APPROVED',
                date__gte=start_date,
                date__lte=end_date,
            )
            if category is not None:
                expenses = expenses.filter(category=category)
            total = float(expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0'))
            for budget in grouped:
                budget._spent_amount_cache = total

    def validate(self, attrs):
        period = attrs.get('period', getattr(self.instance, 'period', 'MONTHLY'))
        start_provided = 'start_date' in attrs
        end_provided = 'end_date' in attrs
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        period_changed = self.instance is not None and period != self.instance.period

        if not start_date:
            start_date, derived_end = derive_budget_date_range(period)
            end_date = end_date or derived_end
        elif not end_date or (start_provided and not end_provided) or (period_changed and not end_provided):
            _, end_date = derive_budget_date_range(period, start_date)

        attrs['start_date'] = start_date
        attrs['end_date'] = end_date

        if start_date > end_date:
            raise serializers.ValidationError({'end_date': 'End date must be on or after start date.'})

        is_active = attrs.get('is_active', getattr(self.instance, 'is_active', True))
        category = attrs.get('category', getattr(self.instance, 'category', None))
        organization = getattr(self.instance, 'organization', None)
        request = self.context.get('request')
        if organization is None and request is not None:
            member = get_active_membership(request.user, request)
            organization = member.organization if member else None

        if is_active and organization and category:
            overlapping = Budget.objects.filter(
                organization=organization,
                category=category,
                is_active=True,
                start_date__lte=end_date,
                end_date__gte=start_date,
            )
            if self.instance:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            if overlapping.exists():
                raise serializers.ValidationError(OVERLAP_MESSAGE)

        return attrs

    def _get_spent_amount(self, obj):
        cached = getattr(obj, '_spent_amount_cache', None)
        if cached is not None:
            return cached

        from expenses.models import Expense

        self.ensure_effective_dates(obj)

        expenses = Expense.objects.filter(
            organization_id=obj.organization_id,
            status='APPROVED',
            date__gte=obj.start_date,
            date__lte=obj.end_date,
        )
        if obj.category != 'ALL':
            expenses = expenses.filter(category=obj.category)
        total = float(expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0'))
        obj._spent_amount_cache = total
        return total

    def get_spent_amount(self, obj):
        return self._get_spent_amount(obj)

    def get_percentage_used(self, obj):
        spent = self._get_spent_amount(obj)
        return round((spent / float(obj.amount)) * 100, 1) if float(obj.amount) > 0 else 0

    def get_remaining_amount(self, obj):
        return float(obj.amount) - self._get_spent_amount(obj)


class BudgetAlertSerializer(serializers.ModelSerializer):
    budget_name = serializers.CharField(source='budget.name', read_only=True)

    class Meta:
        model = BudgetAlert
        fields = [
            'id', 'budget', 'budget_name', 'alert_type', 'percentage',
            'amount_spent', 'message', 'is_read', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
