from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Q
from decimal import Decimal
from .models import Budget, BudgetAlert
from .serializers import BudgetSerializer, BudgetAlertSerializer
from .emails import send_budget_alert_email
from notifications.utils import notify_budget_alert, notify_budget_exceeded
from organizations.context import get_active_membership
from organizations.models import OrganizationMember
from expenses.categories import REAL_EXPENSE_CATEGORY_CODES


class BudgetViewSet(viewsets.ModelViewSet):
    serializer_class = BudgetSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return budgets for user's organization"""
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Budget.objects.all().select_related('organization', 'created_by')

        member = get_active_membership(user, self.request)
        if member:
            return Budget.objects.filter(organization=member.organization).select_related('organization', 'created_by')
        return Budget.objects.none()
    
    def perform_create(self, serializer):
        """Create budget and associate with user's organization"""
        user = self.request.user
        member = get_active_membership(user, self.request)
        
        # Only OWNER can create budgets
        if not member or member.role != 'OWNER':
            raise PermissionDenied('Only owners can create budgets')
        
        serializer.save(
            organization=member.organization,
            created_by=user
        )
        
        # Check if budget needs alert
        self.check_budget_alerts(serializer.instance)
    
    def perform_update(self, serializer):
        """Update budget"""
        user = self.request.user
        member = get_active_membership(user, self.request)
        
        # Only OWNER can update budgets
        if not member or member.role != 'OWNER':
            raise PermissionDenied('Only owners can update budgets')
        
        serializer.save()
        
        # Check if budget needs alert after update
        self.check_budget_alerts(serializer.instance)

    def perform_destroy(self, instance):
        """Delete budget."""
        user = self.request.user
        member = get_active_membership(user, self.request)

        # Only OWNER can delete budgets
        if not ((member and member.role == 'OWNER') or user.is_staff or user.is_superuser):
            raise PermissionDenied('Only owners can delete budgets')

        instance.delete()
    
    def check_budget_alerts(self, budget):
        """Check if budget has crossed threshold and create alerts"""
        serializer = BudgetSerializer(budget)
        percentage_used = serializer.data['percentage_used']
        spent_amount = serializer.data['spent_amount']
        
        # Check if budget exceeded
        if percentage_used >= 100:
            # Check if exceeded alert already exists
            existing_exceeded = BudgetAlert.objects.filter(
                budget=budget,
                alert_type='EXCEEDED'
            ).exists()
            
            if not existing_exceeded:
                # Create alert
                BudgetAlert.objects.create(
                    budget=budget,
                    alert_type='EXCEEDED',
                    percentage=int(percentage_used),
                    amount_spent=spent_amount,
                    message=f"Budget '{budget.name}' has been exceeded! Spent {spent_amount} of {budget.amount} ({percentage_used}%)"
                )
                
                # Send email to owners
                owners = OrganizationMember.objects.filter(
                    organization=budget.organization,
                    role='OWNER'
                ).select_related('user')
                recipients = [owner.user.email for owner in owners if owner.user.email]
                
                if recipients:
                    send_budget_alert_email(budget, spent_amount, recipients)
                
                # Create in-app notifications
                for owner in owners:
                    notify_budget_exceeded(owner.user, budget, spent_amount, percentage_used)
        
        # Check if threshold reached (warning before exceeding)
        elif percentage_used >= budget.alert_threshold:
            # Check if alert already exists for this threshold
            existing_alert = BudgetAlert.objects.filter(
                budget=budget,
                alert_type='THRESHOLD',
                percentage=budget.alert_threshold
            ).exists()
            
            if not existing_alert:
                BudgetAlert.objects.create(
                    budget=budget,
                    alert_type='THRESHOLD',
                    percentage=int(percentage_used),
                    amount_spent=spent_amount,
                    message=f"Budget '{budget.name}' has reached {percentage_used}% of its limit ({spent_amount} of {budget.amount})"
                )
                
                # Create in-app notifications for threshold
                owners = OrganizationMember.objects.filter(
                    organization=budget.organization,
                    role='OWNER'
                ).select_related('user')
                for owner in owners:
                    notify_budget_alert(owner.user, budget, spent_amount, percentage_used)
    
    @action(detail=False, methods=['post'])
    def check_all_alerts(self, request):
        """Manually trigger alert check for all active budgets (OWNER only)"""
        user = request.user
        member = get_active_membership(user, request)

        # Only OWNER can trigger this
        if not member or member.role != 'OWNER':
            return Response(
                {'error': 'Only owners can trigger budget alert checks'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get all active budgets for this organization
        budgets = Budget.objects.filter(
            organization=member.organization,
            is_active=True
        )
        
        alerts_created = 0
        budgets_checked = 0
        
        for budget in budgets:
            budgets_checked += 1
            before_count = BudgetAlert.objects.filter(budget=budget).count()
            self.check_budget_alerts(budget)
            after_count = BudgetAlert.objects.filter(budget=budget).count()
            alerts_created += (after_count - before_count)
        
        return Response({
            'message': 'Budget alert check completed',
            'budgets_checked': budgets_checked,
            'alerts_created': alerts_created
        })
    
    def list(self, request, *args, **kwargs):
        """
        Override list to precompute spent_amount in bulk to avoid BudgetSerializer N+1 queries.

        IMPORTANT: Preserve DRF pagination response shape exactly by using
        paginate_queryset() + get_paginated_response().
        """
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            page_list = list(page)
            BudgetSerializer.precompute_spent_amounts(page_list)
            serializer = self.get_serializer(page_list, many=True)
            return self.get_paginated_response(serializer.data)

        budgets = list(queryset)
        BudgetSerializer.precompute_spent_amounts(budgets)
        serializer = self.get_serializer(budgets, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get budget summary for dashboard"""
        budgets_qs = self.get_queryset().filter(is_active=True)
        budgets = list(budgets_qs)

        total_budgets = budgets_qs.count()
        total_allocated = sum(float(b.amount) for b in budgets)

        BudgetSerializer.precompute_spent_amounts(budgets)
        serializer = self.get_serializer(budgets, many=True)
        data = serializer.data

        total_spent = 0
        if budgets:
            from expenses.models import Expense

            covered_dates = Q()
            for budget in budgets:
                covered_dates |= Q(
                    date__gte=budget.start_date,
                    date__lte=budget.end_date,
                )
            total_spent = float(
                Expense.objects.filter(
                    covered_dates,
                    organization_id=budgets[0].organization_id,
                    status='APPROVED',
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            )

        # Count budgets by status
        at_risk = sum(
            1
            for b in data
            if b['percentage_used'] >= b['alert_threshold'] and b['percentage_used'] < 100
        )
        exceeded = sum(1 for b in data if b['percentage_used'] >= 100)

        return Response({
            'total_budgets': total_budgets,
            'total_allocated': total_allocated,
            'total_spent': total_spent,
            'at_risk_count': at_risk,
            'exceeded_count': exceeded,
            'budgets': data
        })
    
    @action(detail=False, methods=['get'])
    def category_breakdown(self, request):
        """Get spending breakdown by category with budget comparison"""
        from expenses.models import Expense
        
        user = request.user
        member = get_active_membership(user, request)
        
        if not member:
            return Response({'error': 'User not in organization'}, status=400)
        
        # Get all categories
        categories = sorted(REAL_EXPENSE_CATEGORY_CODES)
        
        expense_stats = {
            row['category']: row
            for row in Expense.objects.filter(
                organization=member.organization,
                category__in=categories,
                status='APPROVED'
            ).values('category').annotate(
                total=Sum('amount'),
                count=Count('id')
            )
        }

        budgets_by_category = {}
        active_budgets = Budget.objects.filter(
            organization=member.organization,
            category__in=categories,
            is_active=True
        ).select_related('organization', 'created_by').order_by('category', '-created_at')
        for budget in active_budgets:
            budgets_by_category.setdefault(budget.category, budget)

        category_data = []

        for category in categories:
            stat = expense_stats.get(category, {})
            spent = stat.get('total') or Decimal('0')
            count = stat.get('count') or 0
            budget = budgets_by_category.get(category)
            
            category_info = {
                'category': category,
                'spent': float(spent),
                'expense_count': count,
                'has_budget': budget is not None,
            }
            
            if budget:
                serializer = BudgetSerializer(budget)
                category_info['budget'] = {
                    'id': budget.id,
                    'name': budget.name,
                    'amount': float(budget.amount),
                    'percentage_used': serializer.data['percentage_used'],
                    'remaining': serializer.data['remaining_amount']
                }
            
            category_data.append(category_info)
        
        return Response({
            'categories': category_data,
            'total_categories': len(categories),
            'categories_with_budgets': sum(1 for c in category_data if c['has_budget'])
        })


class BudgetAlertViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BudgetAlertSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return alerts for user's organization budgets"""
        user = self.request.user
        member = get_active_membership(user, self.request)
        if member:
            return BudgetAlert.objects.filter(
                budget__organization=member.organization
            ).select_related('budget', 'budget__organization')
        return BudgetAlert.objects.none()
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark alert as read"""
        alert = self.get_object()
        alert.is_read = True
        alert.save()
        
        serializer = self.get_serializer(alert)
        return Response(serializer.data)
