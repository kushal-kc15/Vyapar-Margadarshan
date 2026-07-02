from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from .models import Expense
from organizations.models import Organization, OrganizationMember
from receipts.models import Receipt
from budgets.models import Budget, BudgetAlert

User = get_user_model()


class ExpenseDashboardMetricsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create test expenses
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        # Today's expenses
        Expense.objects.create(
            user=self.user,
            title='Lunch',
            amount=Decimal('500.00'),
            category='FOOD',
            date=today
        )
        Expense.objects.create(
            user=self.user,
            title='Taxi',
            amount=Decimal('300.00'),
            category='TRANSPORT',
            date=today
        )
        
        # Yesterday's expense
        Expense.objects.create(
            user=self.user,
            title='Office supplies',
            amount=Decimal('1000.00'),
            category='OFFICE',
            date=yesterday
        )
    
    def test_dashboard_metrics_endpoint(self):
        response = self.client.get('/api/expenses/dashboard_metrics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertIn('today', data)
        self.assertIn('week', data)
        self.assertIn('month', data)
    
    def test_today_metrics(self):
        response = self.client.get('/api/expenses/dashboard_metrics/')
        data = response.json()
        
        self.assertEqual(data['today']['total'], 800.0)
        self.assertEqual(data['today']['count'], 2)

    
    def test_expense_list_endpoint(self):
        response = self.client.get('/api/expenses/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.json())
    
    def test_expense_filtering_by_category(self):
        response = self.client.get('/api/expenses/?category=FOOD')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        for expense in data['results']:
            self.assertEqual(expense['category'], 'FOOD')
    
    def test_expense_search(self):
        response = self.client.get('/api/expenses/?search=Lunch')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(len(data['results']) > 0)
    
    def test_expense_pagination(self):
        # Create more expenses
        for i in range(25):
            Expense.objects.create(
                user=self.user,
                title=f'Test Expense {i}',
                amount=Decimal('100.00'),
                category='OTHER',
                date=date.today()
            )
        
        response = self.client.get('/api/expenses/')
        data = response.json()
        self.assertIn('count', data)
        self.assertIn('next', data)
        self.assertIn('results', data)
        self.assertLessEqual(len(data['results']), 20)

    
    def test_create_expense(self):
        manual_date = date.today() - timedelta(days=14)
        data = {
            'title': 'New Test Expense',
            'amount': '500.00',
            'category': 'FOOD',
            'date': manual_date.isoformat(),
            'description': 'Test description'
        }
        response = self.client.post('/api/expenses/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()['title'], 'New Test Expense')
        self.assertEqual(response.json()['date'], manual_date.isoformat())
    
    def test_create_expense_validation(self):
        # Test with invalid amount
        data = {
            'title': 'Invalid Expense',
            'amount': '-100.00',
            'category': 'FOOD',
            'date': date.today().isoformat()
        }
        response = self.client.post('/api/expenses/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ExpenseDashboardMetricsScopeTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username='dashboardowner',
            email='dashboard-owner@example.com',
            password='testpass123',
        )
        self.staff = User.objects.create_user(
            username='dashboardstaff',
            email='dashboard-staff@example.com',
            password='testpass123',
        )
        self.organization = Organization.objects.create(name='Dashboard Org')
        OrganizationMember.objects.create(
            organization=self.organization,
            user=self.owner,
            role='OWNER',
        )
        OrganizationMember.objects.create(
            organization=self.organization,
            user=self.staff,
            role='STAFF',
        )
        self.owner.active_organization = self.organization
        self.owner.save(update_fields=['active_organization'])
        self.staff.active_organization = self.organization
        self.staff.save(update_fields=['active_organization'])

    def create_expense(
        self,
        *,
        user,
        amount,
        status_value='APPROVED',
        expense_date=None,
        title='Dashboard expense',
    ):
        return Expense.objects.create(
            organization=self.organization,
            user=user,
            title=title,
            amount=Decimal(amount),
            category='OTHER',
            date=expense_date or date.today(),
            status=status_value,
        )

    def get_metrics(self, user):
        self.client.force_authenticate(user=user)
        return self.client.get(
            '/api/expenses/dashboard_metrics/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

    def test_owner_metrics_include_approved_staff_expense(self):
        self.create_expense(user=self.staff, amount='125.00')

        response = self.get_metrics(self.owner)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['month']['total'], 125.0)
        self.assertEqual(response.data['month']['count'], 1)

    def test_owner_metrics_exclude_pending_and_rejected_expenses(self):
        self.create_expense(user=self.staff, amount='100.00')
        self.create_expense(
            user=self.staff,
            amount='40.00',
            status_value='PENDING',
            title='Pending expense',
        )
        self.create_expense(
            user=self.staff,
            amount='60.00',
            status_value='REJECTED',
            title='Rejected expense',
        )

        response = self.get_metrics(self.owner)

        self.assertEqual(response.data['month']['total'], 100.0)
        self.assertEqual(response.data['month']['count'], 1)
        today_point = response.data['daily_trend'][-1]
        self.assertEqual(today_point['date'], date.today())
        self.assertEqual(today_point['amount'], 100.0)

    def test_month_comparison_uses_previous_approved_expenses(self):
        month_start = date.today().replace(day=1)
        previous_month_date = month_start - timedelta(days=1)
        self.create_expense(user=self.staff, amount='150.00')
        self.create_expense(
            user=self.staff,
            amount='100.00',
            expense_date=previous_month_date,
            title='Previous month approved',
        )
        self.create_expense(
            user=self.staff,
            amount='400.00',
            status_value='PENDING',
            expense_date=previous_month_date,
            title='Previous month pending',
        )

        response = self.get_metrics(self.owner)

        self.assertEqual(response.data['month']['previous_total'], 100.0)
        self.assertEqual(response.data['month']['growth'], 50.0)

    def test_dashboard_trend_isolated_to_active_workspace(self):
        other_owner = User.objects.create_user(
            username='otherdashboardowner',
            email='other-dashboard-owner@example.com',
            password='testpass123',
        )
        other_organization = Organization.objects.create(name='Other Dashboard Org')
        OrganizationMember.objects.create(
            organization=other_organization,
            user=other_owner,
            role='OWNER',
        )
        Expense.objects.create(
            organization=other_organization,
            user=other_owner,
            title='Other workspace expense',
            amount=Decimal('900.00'),
            category='OTHER',
            date=date.today(),
            status='APPROVED',
        )
        self.create_expense(user=self.staff, amount='75.00')

        response = self.get_metrics(self.owner)

        self.assertEqual(response.data['month']['total'], 75.0)
        self.assertEqual(response.data['daily_trend'][-1]['amount'], 75.0)

    def test_dashboard_trend_empty_data_is_safe(self):
        response = self.get_metrics(self.owner)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['month']['total'], 0.0)
        self.assertEqual(response.data['month']['count'], 0)
        self.assertEqual(response.data['month']['previous_total'], 0.0)
        self.assertIsNone(response.data['month']['growth'])
        self.assertTrue(response.data['daily_trend'])
        self.assertTrue(all(point['amount'] == 0 for point in response.data['daily_trend']))

    def test_staff_metrics_include_only_their_own_approved_expenses(self):
        self.create_expense(user=self.staff, amount='75.00')
        self.create_expense(user=self.owner, amount='200.00')

        response = self.get_metrics(self.staff)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['month']['total'], 75.0)
        self.assertEqual(response.data['month']['count'], 1)

    def test_staff_metrics_exclude_their_pending_and_rejected_expenses(self):
        self.create_expense(user=self.staff, amount='90.00')
        self.create_expense(
            user=self.staff,
            amount='30.00',
            status_value='PENDING',
            title='Pending staff expense',
        )
        self.create_expense(
            user=self.staff,
            amount='20.00',
            status_value='REJECTED',
            title='Rejected staff expense',
        )

        response = self.get_metrics(self.staff)

        self.assertEqual(response.data['month']['total'], 90.0)
        self.assertEqual(response.data['month']['count'], 1)

    def test_month_metrics_use_expense_date(self):
        month_start = date.today().replace(day=1)
        previous_month_date = month_start - timedelta(days=1)
        self.create_expense(
            user=self.staff,
            amount='55.00',
            expense_date=date.today(),
            title='Current month expense',
        )
        self.create_expense(
            user=self.staff,
            amount='145.00',
            expense_date=previous_month_date,
            title='Previous month expense created now',
        )

        response = self.get_metrics(self.owner)

        self.assertEqual(response.data['month']['total'], 55.0)
        self.assertEqual(response.data['month']['count'], 1)


class ExpenseStatusPermissionTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username='staffuser',
            email='staff@example.com',
            password='testpass123',
        )
        self.owner = User.objects.create_user(
            username='expenseowner',
            email='expense-owner@example.com',
            password='testpass123',
        )
        self.organization = Organization.objects.create(name='Expense Org')
        OrganizationMember.objects.create(
            organization=self.organization,
            user=self.staff,
            role='STAFF',
        )
        OrganizationMember.objects.create(
            organization=self.organization,
            user=self.owner,
            role='OWNER',
        )
        self.staff.active_organization = self.organization
        self.staff.save(update_fields=['active_organization'])
        self.owner.active_organization = self.organization
        self.owner.save(update_fields=['active_organization'])
        self.client.force_authenticate(user=self.staff)

    def create_expense(self, status_value='PENDING', title='Submitted receipt'):
        return Expense.objects.create(
            organization=self.organization,
            user=self.staff,
            title=title,
            amount=Decimal('42.00'),
            category='FOOD',
            date=date.today(),
            status=status_value,
        )

    def test_submitter_can_patch_own_pending_expense(self):
        expense = self.create_expense()

        response = self.client.patch(
            f'/api/expenses/{expense.id}/',
            {'title': 'Updated receipt', 'vendor': 'Updated vendor'},
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expense.refresh_from_db()
        self.assertEqual(expense.title, 'Updated receipt')
        self.assertEqual(expense.vendor, 'Updated vendor')

    def test_submitter_can_put_own_pending_expense(self):
        expense = self.create_expense()

        response = self.client.put(
            f'/api/expenses/{expense.id}/',
            {
                'title': 'Replaced expense',
                'amount': '84.00',
                'category': 'TRANSPORT',
                'vendor': 'Transit vendor',
                'date': date.today().isoformat(),
                'description': 'Updated with PUT',
            },
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expense.refresh_from_db()
        self.assertEqual(expense.title, 'Replaced expense')
        self.assertEqual(expense.amount, Decimal('84.00'))
        self.assertEqual(expense.category, 'TRANSPORT')
        self.assertEqual(expense.description, 'Updated with PUT')

    def test_submitter_cannot_patch_approved_expense(self):
        expense = self.create_expense(status_value='APPROVED')

        response = self.client.patch(
            f'/api/expenses/{expense.id}/',
            {'title': 'Changed approved expense'},
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Only pending or rejected expenses can be edited.')
        expense.refresh_from_db()
        self.assertEqual(expense.title, 'Submitted receipt')

    @patch('expenses.views.notify_pending_approval')
    def test_submitter_can_patch_rejected_expense_and_resubmit(self, notify_pending):
        expense = self.create_expense(status_value='REJECTED')
        expense.reviewed_by = self.owner
        expense.rejection_reason = 'Receipt was blurry'
        expense.save(update_fields=['reviewed_by', 'rejection_reason'])

        response = self.client.patch(
            f'/api/expenses/{expense.id}/',
            {'title': 'Corrected rejected expense', 'vendor': 'Corrected vendor'},
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expense.refresh_from_db()
        self.assertEqual(expense.title, 'Corrected rejected expense')
        self.assertEqual(expense.vendor, 'Corrected vendor')
        self.assertEqual(expense.status, 'PENDING')
        self.assertIsNone(expense.reviewed_by)
        self.assertIsNone(expense.reviewed_at)
        self.assertEqual(expense.rejection_reason, '')
        self.assertEqual(response.data['status'], 'PENDING')
        notify_pending.assert_called_once()

    def test_owner_cannot_patch_another_users_expense_in_any_status(self):
        self.client.force_authenticate(user=self.owner)

        for expense_status in ('PENDING', 'APPROVED', 'REJECTED'):
            with self.subTest(expense_status=expense_status):
                expense = self.create_expense(
                    status_value=expense_status,
                    title=f'{expense_status} staff expense',
                )

                response = self.client.patch(
                    f'/api/expenses/{expense.id}/',
                    {'title': 'Owner changed this expense'},
                    format='json',
                    HTTP_X_ORGANIZATION_ID=str(self.organization.id),
                )

                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                self.assertEqual(
                    response.data['error'],
                    'Only the submitter can edit this expense.'
                )
                expense.refresh_from_db()
                self.assertEqual(expense.title, f'{expense_status} staff expense')

    def test_status_and_user_remain_read_only_during_pending_update(self):
        expense = self.create_expense()

        response = self.client.patch(
            f'/api/expenses/{expense.id}/',
            {
                'status': 'APPROVED',
                'user': self.owner.id,
                'title': 'Updated receipt',
            },
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expense.refresh_from_db()
        self.assertEqual(expense.user_id, self.staff.id)
        self.assertEqual(expense.status, 'PENDING')
        self.assertEqual(expense.title, 'Updated receipt')
        self.assertEqual(response.data['status'], 'PENDING')


class ExpenseApprovalDecisionTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username='approvalowner',
            email='approval-owner@example.com',
            password='testpass123',
        )
        self.staff = User.objects.create_user(
            username='approvalstaff',
            email='approval-staff@example.com',
            password='testpass123',
        )
        self.organization = Organization.objects.create(name='Approval Org')
        OrganizationMember.objects.create(
            organization=self.organization,
            user=self.owner,
            role='OWNER',
        )
        OrganizationMember.objects.create(
            organization=self.organization,
            user=self.staff,
            role='STAFF',
        )
        self.owner.active_organization = self.organization
        self.owner.save(update_fields=['active_organization'])
        self.staff.active_organization = self.organization
        self.staff.save(update_fields=['active_organization'])

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def create_expense(
        self,
        user=None,
        status_value='PENDING',
        title='Approval expense',
        amount='50.00',
    ):
        return Expense.objects.create(
            organization=self.organization,
            user=user or self.staff,
            title=title,
            amount=Decimal(amount),
            category='OTHER',
            vendor='Approval Vendor',
            date=date.today(),
            status=status_value,
        )

    def test_staff_cannot_approve_or_reject(self):
        expense = self.create_expense()
        self.authenticate(self.staff)

        approve_response = self.client.post(
            f'/api/expenses/{expense.id}/approve/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )
        reject_response = self.client.post(
            f'/api/expenses/{expense.id}/reject/',
            {'reason': 'Not valid'},
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(approve_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(reject_response.status_code, status.HTTP_403_FORBIDDEN)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'PENDING')

    def test_owner_cannot_approve_or_reject_own_expense(self):
        expense = self.create_expense(user=self.owner)
        self.authenticate(self.owner)

        approve_response = self.client.post(
            f'/api/expenses/{expense.id}/approve/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )
        reject_response = self.client.post(
            f'/api/expenses/{expense.id}/reject/',
            {'reason': 'Own expense'},
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(approve_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(reject_response.status_code, status.HTTP_403_FORBIDDEN)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'PENDING')

    @patch('expenses.views.notify_expense_approved')
    def test_owner_can_approve_another_users_pending_expense(self, notify):
        expense = self.create_expense()
        self.authenticate(self.owner)

        response = self.client.post(
            f'/api/expenses/{expense.id}/approve/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'APPROVED')
        self.assertEqual(expense.reviewed_by_id, self.owner.id)
        self.assertIsNotNone(expense.reviewed_at)
        self.assertEqual(expense.rejection_reason, '')
        notify.assert_called_once()

    @patch('budgets.views.send_budget_alert_email')
    @patch('expenses.views.notify_expense_approved')
    def test_approved_expense_triggers_category_and_all_budget_alerts(self, notify, send_email):
        expense = self.create_expense(amount='50.00')
        for name, category in [('Other Budget', 'OTHER'), ('Overall Budget', 'ALL')]:
            Budget.objects.create(
                organization=self.organization,
                name=name,
                amount=Decimal('50.00'),
                period='DAILY',
                category=category,
                alert_threshold=80,
                start_date=date.today(),
                end_date=date.today(),
                created_by=self.owner,
            )
        self.authenticate(self.owner)

        response = self.client.post(
            f'/api/expenses/{expense.id}/approve/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        alerted_categories = set(BudgetAlert.objects.values_list('budget__category', flat=True))
        self.assertEqual(alerted_categories, {'OTHER', 'ALL'})
        self.assertEqual(BudgetAlert.objects.filter(alert_type='EXCEEDED').count(), 2)

    @patch('expenses.views.notify_expense_rejected')
    def test_owner_can_reject_another_users_pending_expense(self, notify):
        expense = self.create_expense()
        self.authenticate(self.owner)

        response = self.client.post(
            f'/api/expenses/{expense.id}/reject/',
            {'reason': 'Insufficient evidence'},
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'REJECTED')
        self.assertEqual(expense.reviewed_by_id, self.owner.id)
        self.assertIsNotNone(expense.reviewed_at)
        self.assertEqual(expense.rejection_reason, 'Insufficient evidence')
        notify.assert_called_once_with(expense, self.owner, 'Insufficient evidence')

    def test_metadata_fields_are_read_only_in_update_requests(self):
        expense = self.create_expense()
        self.authenticate(self.staff)

        response = self.client.patch(
            f'/api/expenses/{expense.id}/',
            {
                'title': 'Attempt to change title',
                'reviewed_by': self.owner.id,
                'reviewed_at': '1999-01-01T00:00:00Z',
                'rejection_reason': 'Should not be set via patch',
            },
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        # staff can patch pending expense fields they own
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expense.refresh_from_db()
        self.assertIsNone(expense.reviewed_by)
        self.assertIsNone(expense.reviewed_at)
        self.assertEqual(expense.rejection_reason, '')

    @patch('expenses.views.notify_expense_approved')
    @patch('expenses.views.notify_expense_rejected')
    def test_approved_expense_cannot_be_decided_again(
        self,
        notify_rejected,
        notify_approved,
    ):
        expense = self.create_expense()
        self.authenticate(self.owner)

        first_response = self.client.post(
            f'/api/expenses/{expense.id}/approve/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )
        second_approve = self.client.post(
            f'/api/expenses/{expense.id}/approve/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )
        reject_response = self.client.post(
            f'/api/expenses/{expense.id}/reject/',
            {'reason': 'Too late'},
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_approve.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(reject_response.status_code, status.HTTP_400_BAD_REQUEST)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'APPROVED')
        notify_approved.assert_called_once()
        notify_rejected.assert_not_called()

    @patch('expenses.views.notify_expense_approved')
    @patch('expenses.views.notify_expense_rejected')
    def test_rejected_expense_cannot_be_decided_again(
        self,
        notify_rejected,
        notify_approved,
    ):
        expense = self.create_expense()
        self.authenticate(self.owner)

        first_response = self.client.post(
            f'/api/expenses/{expense.id}/reject/',
            {'reason': 'Rejected once'},
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )
        approve_response = self.client.post(
            f'/api/expenses/{expense.id}/approve/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )
        second_reject = self.client.post(
            f'/api/expenses/{expense.id}/reject/',
            {'reason': 'Rejected twice'},
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(approve_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(second_reject.status_code, status.HTTP_400_BAD_REQUEST)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'REJECTED')
        notify_rejected.assert_called_once()
        notify_approved.assert_not_called()

    def test_pending_queue_contains_only_other_users_pending_expenses(self):
        staff_pending = self.create_expense(title='Staff pending')
        owner_pending = self.create_expense(user=self.owner, title='Owner pending')
        self.create_expense(status_value='APPROVED', title='Staff approved')
        self.create_expense(status_value='REJECTED', title='Staff rejected')
        self.authenticate(self.owner)

        response = self.client.get(
            '/api/expenses/pending_approvals/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expense_ids = {item['id'] for item in response.data}
        self.assertEqual(expense_ids, {staff_pending.id})
        self.assertNotIn(owner_pending.id, expense_ids)

    @patch('expenses.views.notify_pending_approval')
    @patch('expenses.views.notify_expense_approved')
    @patch('expenses.views.notify_expense_rejected')
    def test_rejected_expense_can_be_resubmitted_and_reviewed_again(
        self,
        notify_rejected,
        notify_approved,
        notify_pending,
    ):
        expense = self.create_expense(title='Needs correction')
        self.authenticate(self.owner)

        reject_response = self.client.post(
            f'/api/expenses/{expense.id}/reject/',
            {'reason': 'Receipt amount does not match'},
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(reject_response.status_code, status.HTTP_200_OK)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'REJECTED')

        self.authenticate(self.staff)
        resubmit_response = self.client.patch(
            f'/api/expenses/{expense.id}/',
            {'amount': '55.00', 'description': 'Corrected amount and receipt note'},
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(resubmit_response.status_code, status.HTTP_200_OK)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'PENDING')
        self.assertEqual(expense.amount, Decimal('55.00'))
        self.assertEqual(expense.rejection_reason, '')
        notify_pending.assert_called_once()

        self.authenticate(self.owner)
        approve_response = self.client.post(
            f'/api/expenses/{expense.id}/approve/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'APPROVED')
        notify_rejected.assert_called_once()
        notify_approved.assert_called_once()

    @patch('expenses.views.notify_expense_approved')
    @patch('expenses.views.notify_expense_rejected')
    def test_only_approved_decision_appears_in_analytics(
        self,
        notify_rejected,
        notify_approved,
    ):
        approved_expense = self.create_expense(title='Approved report row', amount='70.00')
        rejected_expense = self.create_expense(title='Rejected report row', amount='30.00')
        self.authenticate(self.owner)

        approve_response = self.client.post(
            f'/api/expenses/{approved_expense.id}/approve/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )
        reject_response = self.client.post(
            f'/api/expenses/{rejected_expense.id}/reject/',
            {'reason': 'Exclude from reports'},
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )
        response = self.client.get(
            '/api/analytics/overview/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(reject_response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['transaction_count'], 1)
        self.assertEqual(response.data['total_spent'], 70.0)


class ExpenseReceiptMetadataTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='receiptmetadatauser',
            email='receipt-metadata@example.com',
            password='testpass123',
        )
        self.organization = Organization.objects.create(name='Receipt Metadata Org')
        OrganizationMember.objects.create(
            organization=self.organization,
            user=self.user,
            role='OWNER',
        )
        self.user.active_organization = self.organization
        self.user.save(update_fields=['active_organization'])
        self.client.force_authenticate(user=self.user)

    def create_expense(self, title):
        return Expense.objects.create(
            organization=self.organization,
            user=self.user,
            title=title,
            amount=Decimal('25.00'),
            category='OTHER',
            date=date.today(),
        )

    def test_expense_exposes_linked_receipt_metadata(self):
        expense = self.create_expense('Expense with receipt')
        receipt = Receipt.objects.create(
            organization=self.organization,
            user=self.user,
            expense=expense,
            image='receipts/2026/06/example.png',
        )

        response = self.client.get(
            f'/api/expenses/{expense.id}/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['receipt_id'], receipt.id)
        expected_url = 'http://testserver/media/receipts/2026/06/example.png'
        self.assertEqual(response.data['receipt_url'], expected_url)
        self.assertEqual(response.data['receipt'], expected_url)

    def test_expense_without_receipt_exposes_null_metadata(self):
        expense = self.create_expense('Expense without receipt')

        response = self.client.get(
            f'/api/expenses/{expense.id}/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['receipt_id'])
        self.assertIsNone(response.data['receipt_url'])
        self.assertIsNone(response.data['receipt'])
