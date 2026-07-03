from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta

from .models import Expense
from .serializers import ExpenseSerializer
from activity_logs.utils import log_activity
from notifications.utils import notify_expense_approved, notify_expense_rejected, notify_pending_approval
from organizations.context import get_active_membership
from organizations.models import OrganizationMember
from analytics.anomaly_notifications import notify_owners_if_expense_is_unusual


class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'status', 'date']
    search_fields = ['title', 'description']
    ordering_fields = ['date', 'amount', 'created_at']
    ordering = ['-date', '-created_at']
    
    def get_queryset(self):
        """
        Return expenses based on user role:
        - OWNER/MANAGER: All organization expenses
        - STAFF: Only their own expenses
        """
        user = self.request.user
        member = get_active_membership(user, self.request)
        queryset = Expense.objects.select_related('user', 'organization', 'receipt')

        if member and member.role == 'OWNER':
            return queryset.filter(organization=member.organization)
        if member:
            return queryset.filter(user=user, organization=member.organization)
        return queryset.filter(user=user)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)

        with transaction.atomic():
            queryset = self.filter_queryset(self.get_queryset()).select_for_update()
            lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
            lookup_value = self.kwargs[lookup_url_kwarg]
            expense = get_object_or_404(
                queryset,
                **{self.lookup_field: lookup_value}
            )
            self.check_object_permissions(request, expense)

            if expense.user_id != request.user.id:
                return Response(
                    {'error': 'Only the submitter can edit this expense.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            original_status = expense.status
            if original_status not in {'PENDING', 'REJECTED'}:
                return Response(
                    {'error': 'Only pending or rejected expenses can be edited.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            serializer = self.get_serializer(
                expense,
                data=request.data,
                partial=partial
            )
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            expense = serializer.instance

            if original_status == 'REJECTED':
                expense.status = 'PENDING'
                expense.reviewed_by = None
                expense.reviewed_at = None
                expense.rejection_reason = ''
                expense.save(update_fields=[
                    'status',
                    'reviewed_by',
                    'reviewed_at',
                    'rejection_reason',
                    'updated_at',
                ])

                member = get_active_membership(request.user, request)
                if member:
                    log_activity(
                        organization=member.organization,
                        user=request.user,
                        action_type='EXPENSE_UPDATED',
                        description=(
                            f"{request.user.get_full_name()} resubmitted expense: "
                            f"{expense.title} (रू {expense.amount})"
                        ),
                        metadata={'expense_id': expense.id, 'status': 'PENDING'}
                    )
                    owners = OrganizationMember.objects.filter(
                        organization=member.organization,
                        role='OWNER'
                    )
                    notify_pending_approval(owners, expense)

            if getattr(expense, '_prefetched_objects_cache', None):
                expense._prefetched_objects_cache = {}

        return Response(serializer.data)
    
    def perform_create(self, serializer):
        user = self.request.user
        member = get_active_membership(user, self.request)
        
        # Set status based on role
        if member and member.role == 'STAFF':
            # Staff expenses need approval
            expense = serializer.save(
                user=user,
                organization=member.organization,
                status='PENDING'
            )
            # Log activity
            log_activity(
                organization=member.organization,
                user=user,
                action_type='EXPENSE_CREATED',
                description=f"{user.get_full_name()} created expense: {expense.title} (रू {expense.amount})",
                metadata={'expense_id': expense.id, 'status': 'PENDING'}
            )
            # Notify owners about pending approval
            owners = OrganizationMember.objects.filter(
                organization=member.organization,
                role='OWNER'
            )
            notify_pending_approval(owners, expense)
            notify_owners_if_expense_is_unusual(expense)
        else:
            # Owner expenses are auto-approved
            if member:
                expense = serializer.save(
                    user=user,
                    organization=member.organization,
                    status='APPROVED'
                )
                # Check budgets for auto-approved expenses
                self.check_budgets_for_expense(expense)
                # Log activity
                log_activity(
                    organization=member.organization,
                    user=user,
                    action_type='EXPENSE_CREATED',
                    description=f"{user.get_full_name()} created expense: {expense.title} (रू {expense.amount})",
                    metadata={'expense_id': expense.id, 'status': 'APPROVED'}
                )
            else:
                # User without organization (shouldn't happen, but handle it)
                serializer.save(user=user, status='APPROVED')
    
    def check_budgets_for_expense(self, expense):
        """Check if expense causes any budget to exceed and trigger alerts"""
        from budgets.models import Budget
        from budgets.views import BudgetViewSet
        
        # Find active budgets for this category and organization
        budgets = Budget.objects.filter(
            Q(category=expense.category) | Q(category='ALL'),
            organization=expense.organization,
            is_active=True,
            start_date__lte=expense.date,
            end_date__gte=expense.date
        )
        
        # Check each budget
        budget_viewset = BudgetViewSet()
        for budget in budgets:
            budget_viewset.check_budget_alerts(budget)
    
    @action(detail=False, methods=['get'])
    def dashboard_metrics(self, request):
        """
        Calculate dashboard metrics:
        - OWNER: Organization-wide metrics
        - STAFF: Personal metrics only
        """
        user = request.user
        today = timezone.localdate()
        
        member = get_active_membership(user, request)

        if member and member.role == 'OWNER':
            base_filter = Q(organization=member.organization, status='APPROVED')
        elif member:
            base_filter = Q(
                user=user,
                organization=member.organization,
                status='APPROVED',
            )
        else:
            base_filter = Q(user=user, status='APPROVED')
        
        # Today's metrics
        today_expenses = Expense.objects.filter(
            base_filter,
            date=today
        ).aggregate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Yesterday's metrics for comparison
        yesterday = today - timedelta(days=1)
        yesterday_expenses = Expense.objects.filter(
            base_filter,
            date=yesterday
        ).aggregate(
            total=Sum('amount')
        )
        
        # This week's metrics
        week_start = today - timedelta(days=today.weekday())
        week_expenses = Expense.objects.filter(
            base_filter,
            date__gte=week_start,
            date__lte=today
        ).aggregate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Last week's metrics for comparison
        last_week_start = week_start - timedelta(days=7)
        last_week_end = week_start - timedelta(days=1)
        last_week_expenses = Expense.objects.filter(
            base_filter,
            date__gte=last_week_start,
            date__lte=last_week_end
        ).aggregate(
            total=Sum('amount')
        )
        
        # This month's metrics
        month_start = today.replace(day=1)
        month_expenses = Expense.objects.filter(
            base_filter,
            date__gte=month_start,
            date__lte=today
        ).aggregate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Last month's metrics for comparison
        last_month_end = month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        last_month_expenses = Expense.objects.filter(
            base_filter,
            date__gte=last_month_start,
            date__lte=last_month_end
        ).aggregate(
            total=Sum('amount')
        )
        
        # Calculate growth percentages
        def calculate_growth(current, previous):
            if previous and previous > 0:
                return round(((current - previous) / previous) * 100, 1)
            return 0
        
        today_total = float(today_expenses['total'] or 0)
        yesterday_total = float(yesterday_expenses['total'] or 0)
        week_total = float(week_expenses['total'] or 0)
        last_week_total = float(last_week_expenses['total'] or 0)
        month_total = float(month_expenses['total'] or 0)
        last_month_total = float(last_month_expenses['total'] or 0)

        daily_rows = Expense.objects.filter(
            base_filter,
            date__gte=month_start,
            date__lte=today,
        ).values('date').annotate(total=Sum('amount')).order_by('date')
        daily_totals = {
            row['date']: float(row['total'] or 0)
            for row in daily_rows
        }
        daily_trend = []
        trend_date = month_start
        while trend_date <= today:
            daily_trend.append({
                'date': trend_date,
                'amount': daily_totals.get(trend_date, 0),
            })
            trend_date += timedelta(days=1)
        
        return Response({
            'today': {
                'total': today_total,
                'count': today_expenses['count'] or 0,
                'growth': calculate_growth(today_total, yesterday_total)
            },
            'week': {
                'total': week_total,
                'count': week_expenses['count'] or 0,
                'growth': calculate_growth(week_total, last_week_total)
            },
            'month': {
                'total': month_total,
                'count': month_expenses['count'] or 0,
                'previous_total': last_month_total,
                'growth': (
                    calculate_growth(month_total, last_month_total)
                    if last_month_total > 0
                    else None
                ),
            },
            'daily_trend': daily_trend,
        })
    
    @action(detail=False, methods=['get'])
    def my_expenses(self, request):
        """Get current user's expenses with status breakdown"""
        user = request.user
        
        # Get all user's expenses
        expenses = self.get_queryset()
        
        # Count by status
        pending_count = expenses.filter(status='PENDING').count()
        approved_count = expenses.filter(status='APPROVED').count()
        rejected_count = expenses.filter(status='REJECTED').count()
        
        # Calculate totals
        pending_total = expenses.filter(status='PENDING').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        approved_total = expenses.filter(status='APPROVED').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        return Response({
            'pending': {
                'count': pending_count,
                'total': float(pending_total)
            },
            'approved': {
                'count': approved_count,
                'total': float(approved_total)
            },
            'rejected': {
                'count': rejected_count
            },
            'total_count': expenses.count()
        })
    
    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        """Get all pending expenses in the organization for approval (OWNER only)"""
        user = request.user
        
        member = get_active_membership(user, request)

        if not member or member.role != 'OWNER':
            return Response(
                {'error': 'Only owners can view pending approvals'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get all pending expenses in the organization (excluding own expenses)
        pending_expenses = Expense.objects.filter(
            organization=member.organization,
            status='PENDING'
        ).exclude(user=user).select_related('user', 'organization').order_by('-date', '-created_at')
        
        serializer = self.get_serializer(pending_expenses, many=True)
        return Response(serializer.data)

    def _decide_expense(self, request, pk, decision):
        user = request.user
        approving = decision == 'APPROVED'
        action_label = 'approve' if approving else 'reject'

        with transaction.atomic():
            member = get_active_membership(user, request)
            if not member or member.role != 'OWNER':
                return Response(
                    {'error': f'Only owners can {action_label} expenses'},
                    status=status.HTTP_403_FORBIDDEN
                )

            try:
                expense = self.get_queryset().select_for_update().get(pk=pk)
            except Expense.DoesNotExist:
                return Response(
                    {'error': 'Expense not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            if expense.user_id == user.id:
                return Response(
                    {'error': f'You cannot {action_label} your own expenses'},
                    status=status.HTTP_403_FORBIDDEN
                )

            if expense.status != 'PENDING':
                return Response(
                    {'error': f'Only pending expenses can be {decision.lower()}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            expense.status = decision

            now = timezone.now()
            if approving:
                expense.reviewed_by = user
                expense.reviewed_at = now
                expense.rejection_reason = ''
            else:
                rejection_reason = (request.data.get('reason', '') or '').strip()
                expense.reviewed_by = user
                expense.reviewed_at = now
                expense.rejection_reason = rejection_reason

            expense.save(
                update_fields=[
                    'status',
                    'updated_at',
                    'reviewed_by',
                    'reviewed_at',
                    'rejection_reason',
                ]
            )

            if approving:
                self.check_budgets_for_expense(expense)
                notify_expense_approved(expense, user)

                metadata = {'expense_id': expense.id, 'approved_by': user.id}
                action_type = 'EXPENSE_APPROVED'
            else:
                notify_expense_rejected(expense, user, expense.rejection_reason)

                metadata = {
                    'expense_id': expense.id,
                    'rejected_by': user.id,
                    'reason': expense.rejection_reason,
                }
                action_type = 'EXPENSE_REJECTED'

            log_activity(
                organization=member.organization,
                user=user,
                action_type=action_type,
                description=(
                    f"{user.get_full_name()} {decision.lower()} expense: "
                    f"{expense.title} (रू {expense.amount}) by "
                    f"{expense.user.get_full_name()}"
                ),
                metadata=metadata
            )

            serializer = self.get_serializer(expense)
            return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a pending expense (OWNER only)"""
        return self._decide_expense(request, pk, 'APPROVED')

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a pending expense with reason (OWNER only)"""
        return self._decide_expense(request, pk, 'REJECTED')

    @action(detail=False, methods=['get'])
    def vendor_analytics(self, request):
        """Get vendor spending analytics"""
        user = request.user
        
        member = get_active_membership(user, request)

        if member and member.role == 'OWNER':
            expenses = Expense.objects.filter(
                organization=member.organization,
                status='APPROVED',
                vendor__isnull=False
            ).exclude(vendor='')
        elif member:
            expenses = Expense.objects.filter(
                user=user,
                organization=member.organization,
                vendor__isnull=False
            ).exclude(vendor='')
        else:
            expenses = Expense.objects.filter(
                user=user,
                vendor__isnull=False
            ).exclude(vendor='')
        
        # Group by vendor and calculate totals
        from django.db.models import Sum, Count
        vendor_stats = expenses.values('vendor').annotate(
            total_amount=Sum('amount'),
            transaction_count=Count('id')
        ).order_by('-total_amount')
        
        # Convert to list and format
        vendors = []
        for stat in vendor_stats:
            vendors.append({
                'vendor': stat['vendor'],
                'total_amount': float(stat['total_amount']),
                'transaction_count': stat['transaction_count']
            })
        
        # Calculate overall stats
        total_vendors = len(vendors)
        total_spent = sum(v['total_amount'] for v in vendors)
        
        return Response({
            'vendors': vendors,
            'total_vendors': total_vendors,
            'total_spent': total_spent
        })


    @action(detail=False, methods=['get'])
    def export_csv(self, request):
        """Export expenses to CSV"""
        from django.http import HttpResponse
        import csv
        
        user = request.user
        
        member = get_active_membership(user, request)

        if member and member.role == 'OWNER':
            expenses = Expense.objects.filter(organization=member.organization)
        elif member:
            expenses = Expense.objects.filter(user=user, organization=member.organization)
        else:
            expenses = Expense.objects.filter(user=user)
        
        # Apply filters from query params
        status_filter = request.query_params.get('status')
        category_filter = request.query_params.get('category')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        search = request.query_params.get('search')
        
        if status_filter:
            expenses = expenses.filter(status=status_filter.upper())
        if category_filter:
            expenses = expenses.filter(category=category_filter.upper())
        if date_from:
            expenses = expenses.filter(date__gte=date_from)
        if date_to:
            expenses = expenses.filter(date__lte=date_to)
        if search:
            expenses = expenses.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(vendor__icontains=search)
                | Q(user__username__icontains=search)
                | Q(user__email__icontains=search)
            )
        
        # Order by date
        expenses = expenses.select_related('user', 'organization').order_by('-date', '-created_at')
        total_amount = expenses.aggregate(total=Sum('amount'))['total'] or 0
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response.write('\ufeff')
        filename = f'expenses_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow([
            'Expense ID',
            'Organization',
            'Date',
            'Title',
            'Category Code',
            'Category Label',
            'Vendor',
            'Amount NPR',
            'Status Code',
            'Status Label',
            'Description',
            'Submitted By Name',
            'Submitted By Username',
            'Submitted By Email',
            'Created At',
            'Updated At',
            'Receipt Attached',
        ])
        
        # Write data
        for expense in expenses:
            created_at = timezone.localtime(expense.created_at).strftime('%Y-%m-%d %H:%M:%S')
            updated_at = timezone.localtime(expense.updated_at).strftime('%Y-%m-%d %H:%M:%S')
            writer.writerow([
                expense.id,
                expense.organization.name if expense.organization else '',
                expense.date.strftime('%Y-%m-%d'),
                expense.title,
                expense.category,
                expense.get_category_display(),
                expense.vendor or '',
                f'{expense.amount:.2f}',
                expense.status,
                expense.get_status_display(),
                expense.description or '',
                expense.user.get_full_name() or expense.user.username,
                expense.user.username,
                expense.user.email,
                created_at,
                updated_at,
                'Yes' if hasattr(expense, 'receipt') else 'No',
            ])

        writer.writerow([])
        writer.writerow(['TOTAL', '', '', '', '', '', '', f'{total_amount:.2f}', '', '', '', '', '', '', '', '', ''])
        
        return response
