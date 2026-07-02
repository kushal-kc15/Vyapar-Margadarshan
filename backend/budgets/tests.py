from decimal import Decimal
from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from budgets.emails import send_budget_alert_email
from budgets.models import Budget
from budgets.serializers import BudgetSerializer
from organizations.models import Organization, OrganizationMember
from users.models import User


class BudgetAlertEmailTests(TestCase):
    def test_send_budget_alert_email_handles_missing_dates(self):
        user = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='pass12345',
        )
        organization = Organization.objects.create(name='Test Organization')
        budget = Budget.objects.create(
            organization=organization,
            created_by=user,
            name='Monthly Food Budget',
            amount=Decimal('1000.00'),
            period='MONTHLY',
            category='FOOD',
            start_date=None,
            end_date=None,
        )

        sent = send_budget_alert_email(
            budget=budget,
            current_spending=Decimal('1250.00'),
            recipients=['owner@example.com'],
        )

        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Period:', mail.outbox[0].body)
        self.assertIn(' to ', mail.outbox[0].body)
        self.assertIn('Period', mail.outbox[0].alternatives[0][0])


class BudgetSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='pass12345',
        )
        self.organization = Organization.objects.create(name='Test Organization')

    def test_create_budget_defaults_dates_from_period(self):
        serializer = BudgetSerializer(data={
            'name': 'Monthly Food Budget',
            'amount': '1000.00',
            'period': 'MONTHLY',
            'category': 'FOOD',
            'alert_threshold': 80,
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        budget = serializer.save(
            organization=self.organization,
            created_by=self.user,
        )

        today = timezone.now().date()
        expected_start = today.replace(day=1)
        if today.month == 12:
            expected_end = today.replace(day=31)
        else:
            expected_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

        self.assertEqual(budget.start_date, expected_start)
        self.assertEqual(budget.end_date, expected_end)

    def test_budget_date_range_must_be_ordered(self):
        serializer = BudgetSerializer(data={
            'name': 'Invalid Budget',
            'amount': '1000.00',
            'period': 'MONTHLY',
            'category': 'FOOD',
            'start_date': '2026-02-01',
            'end_date': '2026-01-01',
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('end_date', serializer.errors)


class BudgetPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username='budgetowner',
            email='budgetowner@example.com',
            password='pass12345',
        )
        self.staff = User.objects.create_user(
            username='budgetstaff',
            email='budgetstaff@example.com',
            password='pass12345',
        )
        self.organization = Organization.objects.create(name='Budget Org')
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
        self.budget = Budget.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name='Monthly Food Budget',
            amount=Decimal('1000.00'),
            period='MONTHLY',
            category='FOOD',
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def test_staff_cannot_create_budget(self):
        self._auth(self.staff)

        response = self.client.post(
            '/api/budgets/',
            data={
                'name': 'Staff Budget',
                'amount': '500.00',
                'period': 'MONTHLY',
                'category': 'FOOD',
                'alert_threshold': 80,
                'start_date': '2026-01-01',
                'end_date': '2026-01-31',
            },
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_create_budget(self):
        self._auth(self.owner)

        response = self.client.post(
            '/api/budgets/',
            data={
                'name': 'Owner Budget',
                'amount': '500.00',
                'period': 'MONTHLY',
                'category': 'FOOD',
                'alert_threshold': 80,
                'start_date': '2026-01-01',
                'end_date': '2026-01-31',
            },
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Budget.objects.filter(
                organization=self.organization,
                name='Owner Budget',
            ).exists()
        )

    def test_staff_cannot_update_budget(self):
        self._auth(self.staff)

        response = self.client.patch(
            f'/api/budgets/{self.budget.id}/',
            data={
                'name': 'Updated by staff',
            },
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.budget.refresh_from_db()
        self.assertEqual(self.budget.name, 'Monthly Food Budget')

    def test_owner_can_update_budget(self):
        self._auth(self.owner)

        response = self.client.patch(
            f'/api/budgets/{self.budget.id}/',
            data={
                'name': 'Updated by owner',
            },
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.budget.refresh_from_db()
        self.assertEqual(self.budget.name, 'Updated by owner')

    def test_staff_cannot_pause_resume_budget(self):
        self._auth(self.staff)

        response = self.client.patch(
            f'/api/budgets/{self.budget.id}/',
            data={'is_active': False},
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.budget.refresh_from_db()
        self.assertTrue(self.budget.is_active)

    def test_owner_can_pause_resume_budget(self):
        self._auth(self.owner)

        response = self.client.patch(
            f'/api/budgets/{self.budget.id}/',
            data={'is_active': False},
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.budget.refresh_from_db()
        self.assertFalse(self.budget.is_active)

        response = self.client.patch(
            f'/api/budgets/{self.budget.id}/',
            data={'is_active': True},
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.budget.refresh_from_db()
        self.assertTrue(self.budget.is_active)

    def test_staff_cannot_delete_budget(self):
        self._auth(self.staff)

        response = self.client.delete(
            f'/api/budgets/{self.budget.id}/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Budget.objects.filter(id=self.budget.id).exists())

    def test_owner_can_delete_budget(self):
        self._auth(self.owner)

        response = self.client.delete(
            f'/api/budgets/{self.budget.id}/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Budget.objects.filter(id=self.budget.id).exists())

    def test_legacy_budget_with_null_dates_loads_with_effective_range(self):
        Budget.objects.filter(pk=self.budget.pk).update(start_date=None, end_date=None)
        self._auth(self.owner)

        response = self.client.get(
            '/api/budgets/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.data['results'][0]
        self.assertIsNotNone(row['start_date'])
        self.assertIsNotNone(row['end_date'])

    def test_summary_handles_legacy_budget_with_null_end_date(self):
        Budget.objects.filter(pk=self.budget.pk).update(end_date=None)
        self._auth(self.owner)

        response = self.client.get(
            '/api/budgets/summary/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_budgets'], 1)


class BudgetOverlapRulesTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username='overlapowner',
            email='overlap@example.com',
            password='pass12345',
        )
        self.organization = Organization.objects.create(name='Overlap Org')
        OrganizationMember.objects.create(
            organization=self.organization,
            user=self.owner,
            role='OWNER',
        )
        self.owner.active_organization = self.organization
        self.owner.save(update_fields=['active_organization'])
        self.client.force_authenticate(self.owner)
        self.food_budget = Budget.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name='June Food',
            amount=Decimal('1000.00'),
            period='MONTHLY',
            category='FOOD',
            start_date=timezone.datetime(2027, 6, 1).date(),
            end_date=timezone.datetime(2027, 6, 30).date(),
        )

    def post_budget(self, **overrides):
        payload = {
            'name': 'Budget',
            'amount': '500.00',
            'period': 'MONTHLY',
            'category': 'FOOD',
            'alert_threshold': 80,
            'start_date': '2027-06-15',
        }
        payload.update(overrides)
        return self.client.post(
            '/api/budgets/',
            payload,
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

    def test_same_category_overlapping_active_budget_is_rejected(self):
        response = self.post_budget()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            'An active budget for this category already exists in the selected date range.',
            str(response.data),
        )

    def test_same_category_non_overlapping_budget_is_allowed(self):
        response = self.post_budget(start_date='2027-07-01')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_different_category_and_all_can_share_the_same_period(self):
        transport = self.post_budget(category='TRANSPORT', name='Transport')
        overall = self.post_budget(category='ALL', name='Overall')

        self.assertEqual(transport.status_code, status.HTTP_201_CREATED)
        self.assertEqual(overall.status_code, status.HTTP_201_CREATED)

    def test_update_that_creates_overlap_is_rejected(self):
        july = Budget.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name='July Food',
            amount=Decimal('600.00'),
            period='MONTHLY',
            category='FOOD',
            start_date=timezone.datetime(2027, 7, 1).date(),
            end_date=timezone.datetime(2027, 7, 31).date(),
        )

        response = self.client.patch(
            f'/api/budgets/{july.id}/',
            {'start_date': '2027-06-15'},
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reactivating_overlapping_paused_budget_is_rejected(self):
        paused = Budget.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name='Paused June Food',
            amount=Decimal('700.00'),
            period='MONTHLY',
            category='FOOD',
            start_date=timezone.datetime(2027, 6, 1).date(),
            end_date=timezone.datetime(2027, 6, 30).date(),
            is_active=False,
        )

        response = self.client.patch(
            f'/api/budgets/{paused.id}/',
            {'is_active': True},
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_monthly_start_date_derives_end_date(self):
        response = self.post_budget(
            category='TRAVEL',
            name='June Travel',
            start_date='2027-06-01',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['end_date'], '2027-06-30')

    def test_summary_counts_approved_spend_once_with_all_and_category_budgets(self):
        from expenses.models import Expense

        overall = self.post_budget(
            category='ALL',
            name='Overall June',
            start_date='2027-06-01',
        )
        self.assertEqual(overall.status_code, status.HTTP_201_CREATED)
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Approved meal',
            amount=Decimal('100.00'),
            category='FOOD',
            date=timezone.datetime(2027, 6, 10).date(),
            status='APPROVED',
        )

        response = self.client.get(
            '/api/budgets/summary/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_spent'], 100.0)


class BudgetUsageTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username='usageowner',
            email='usageowner@example.com',
            password='pass12345',
        )
        self.staff = User.objects.create_user(
            username='usagestaff',
            email='usagestaff@example.com',
            password='pass12345',
        )
        self.organization = Organization.objects.create(name='Usage Org')
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

    def _auth_owner(self):
        self.client.force_authenticate(user=self.owner)

    def _get_budget_spent_amount(self, budget_id):
        response = self.client.get(
            f'/api/budgets/{budget_id}/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return Decimal(str(response.data['spent_amount']))

    def _get_budgets_spent_amounts_from_list(self):
        response = self.client.get(
            '/api/budgets/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def test_spent_amount_includes_approved_expenses(self):
        from expenses.models import Expense

        self._auth_owner()
        start_date = timezone.datetime(2026, 1, 1).date()
        end_date = timezone.datetime(2026, 1, 31).date()

        budget = Budget.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name='Approved Budget',
            amount=Decimal('1000.00'),
            period='MONTHLY',
            category='ALL',
            start_date=start_date,
            end_date=end_date,
        )

        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Approved Food',
            amount=Decimal('100.00'),
            category='FOOD',
            date=start_date,
            status='APPROVED',
        )
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Approved Transport',
            amount=Decimal('50.00'),
            category='TRANSPORT',
            date=end_date,
            status='APPROVED',
        )

        spent_amount = self._get_budget_spent_amount(budget.id)
        self.assertEqual(spent_amount, Decimal('150.00'))

    def test_list_endpoint_budget_spent_amount_bulk_approved_only(self):
        from expenses.models import Expense

        self._auth_owner()
        start_date = timezone.datetime(2026, 8, 1).date()
        end_date = timezone.datetime(2026, 8, 31).date()

        budget = Budget.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name='Bulk Approved Only Budget',
            amount=Decimal('1000.00'),
            period='MONTHLY',
            category='ALL',
            start_date=start_date,
            end_date=end_date,
        )

        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Approved Food',
            amount=Decimal('10.00'),
            category='FOOD',
            date=start_date,
            status='APPROVED',
        )
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Pending Food',
            amount=Decimal('20.00'),
            category='FOOD',
            date=start_date,
            status='PENDING',
        )
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Rejected Food',
            amount=Decimal('30.00'),
            category='FOOD',
            date=start_date,
            status='REJECTED',
        )

        budgets_data = self._get_budgets_spent_amounts_from_list()

        # DRF list may return either a list or a paginated object depending on pagination config.
        if isinstance(budgets_data, dict) and 'results' in budgets_data:
            budgets_data = budgets_data['results']

        budget_row = next(b for b in budgets_data if b['id'] == budget.id)
        self.assertEqual(Decimal(str(budget_row['spent_amount'])), Decimal('10.00'))

    def test_period_fallback_daily_counts_today_only(self):
        from expenses.models import Expense

        self._auth_owner()
        today = timezone.now().date()

        budget = Budget.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name='Daily Budget',
            amount=Decimal('1000.00'),
            period='DAILY',
            category='ALL',
            start_date=None,
            end_date=None,
        )

        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Today approved',
            amount=Decimal('11.00'),
            category='FOOD',
            date=today,
            status='APPROVED',
        )
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Yesterday approved',
            amount=Decimal('22.00'),
            category='FOOD',
            date=today - timedelta(days=1),
            status='APPROVED',
        )

        spent_amount = self._get_budget_spent_amount(budget.id)
        self.assertEqual(spent_amount, Decimal('11.00'))

    def test_period_fallback_weekly_counts_current_monday_to_sunday(self):
        from expenses.models import Expense

        self._auth_owner()
        today = timezone.now().date()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)

        budget = Budget.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name='Weekly Budget',
            amount=Decimal('1000.00'),
            period='WEEKLY',
            category='ALL',
            start_date=None,
            end_date=None,
        )

        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Monday approved',
            amount=Decimal('5.00'),
            category='FOOD',
            date=monday,
            status='APPROVED',
        )
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Sunday approved',
            amount=Decimal('7.00'),
            category='FOOD',
            date=sunday,
            status='APPROVED',
        )
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Before Monday approved',
            amount=Decimal('13.00'),
            category='FOOD',
            date=monday - timedelta(days=1),
            status='APPROVED',
        )

        spent_amount = self._get_budget_spent_amount(budget.id)
        self.assertEqual(spent_amount, Decimal('12.00'))

    def test_period_fallback_monthly_counts_current_month(self):
        from expenses.models import Expense

        self._auth_owner()
        today = timezone.now().date()
        first_day = today.replace(day=1)
        # Handle December properly
        if today.month == 12:
            last_day = today.replace(day=31)
        else:
            last_day = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

        budget = Budget.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name='Monthly Budget',
            amount=Decimal('1000.00'),
            period='MONTHLY',
            category='ALL',
            start_date=None,
            end_date=None,
        )

        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='First day approved',
            amount=Decimal('9.00'),
            category='FOOD',
            date=first_day,
            status='APPROVED',
        )
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Last day approved',
            amount=Decimal('10.00'),
            category='FOOD',
            date=last_day,
            status='APPROVED',
        )
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Before first day approved',
            amount=Decimal('100.00'),
            category='FOOD',
            date=first_day - timedelta(days=1),
            status='APPROVED',
        )

        spent_amount = self._get_budget_spent_amount(budget.id)
        self.assertEqual(spent_amount, Decimal('19.00'))

    def test_period_fallback_yearly_counts_current_year(self):
        from expenses.models import Expense

        self._auth_owner()
        today = timezone.now().date()
        year_start = today.replace(month=1, day=1)
        year_end = today.replace(month=12, day=31)

        budget = Budget.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name='Yearly Budget',
            amount=Decimal('1000.00'),
            period='YEARLY',
            category='ALL',
            start_date=None,
            end_date=None,
        )

        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Year start approved',
            amount=Decimal('21.00'),
            category='FOOD',
            date=year_start,
            status='APPROVED',
        )
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Year end approved',
            amount=Decimal('22.00'),
            category='FOOD',
            date=year_end,
            status='APPROVED',
        )
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Before year start approved',
            amount=Decimal('100.00'),
            category='FOOD',
            date=year_start - timedelta(days=1),
            status='APPROVED',
        )

        spent_amount = self._get_budget_spent_amount(budget.id)
        self.assertEqual(spent_amount, Decimal('43.00'))

    def test_non_member_cannot_create_budget(self):
        from expenses.models import Expense  # noqa: F401

        self.client = APIClient()
        non_member = User.objects.create_user(
            username='nonmember',
            email='nonmember@example.com',
            password='pass12345',
        )
        self.client.force_authenticate(user=non_member)

        response = self.client.post(
            '/api/budgets/',
            data={
                'name': 'Non-member Budget',
                'amount': '500.00',
                'period': 'MONTHLY',
                'category': 'FOOD',
                'alert_threshold': 80,
                'start_date': '2026-01-01',
                'end_date': '2026-01-31',
            },
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_spent_amount_excludes_pending_expenses(self):
        from expenses.models import Expense

        self._auth_owner()
        start_date = timezone.datetime(2026, 2, 1).date()
        end_date = timezone.datetime(2026, 2, 28).date()

        budget = Budget.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name='Pending Exclusion Budget',
            amount=Decimal('1000.00'),
            period='MONTHLY',
            category='ALL',
            start_date=start_date,
            end_date=end_date,
        )

        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Pending Food',
            amount=Decimal('200.00'),
            category='FOOD',
            date=start_date,
            status='PENDING',
        )

        spent_amount = self._get_budget_spent_amount(budget.id)
        self.assertEqual(spent_amount, Decimal('0'))

    def test_spent_amount_excludes_rejected_expenses(self):
        from expenses.models import Expense

        self._auth_owner()
        start_date = timezone.datetime(2026, 3, 1).date()
        end_date = timezone.datetime(2026, 3, 31).date()

        budget = Budget.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name='Rejected Exclusion Budget',
            amount=Decimal('1000.00'),
            period='MONTHLY',
            category='ALL',
            start_date=start_date,
            end_date=end_date,
        )

        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Rejected Food',
            amount=Decimal('300.00'),
            category='FOOD',
            date=start_date,
            status='REJECTED',
        )

        spent_amount = self._get_budget_spent_amount(budget.id)
        self.assertEqual(spent_amount, Decimal('0'))

    def test_category_all_includes_approved_expenses_from_all_categories(self):
        from expenses.models import Expense

        self._auth_owner()
        start_date = timezone.datetime(2026, 4, 1).date()
        end_date = timezone.datetime(2026, 4, 30).date()

        budget_all = Budget.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name='ALL Budget',
            amount=Decimal('1000.00'),
            period='MONTHLY',
            category='ALL',
            start_date=start_date,
            end_date=end_date,
        )

        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Approved Food',
            amount=Decimal('80.00'),
            category='FOOD',
            date=start_date,
            status='APPROVED',
        )
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Approved Transport',
            amount=Decimal('120.00'),
            category='TRANSPORT',
            date=end_date,
            status='APPROVED',
        )

        spent_amount = self._get_budget_spent_amount(budget_all.id)
        self.assertEqual(spent_amount, Decimal('200.00'))

    def test_specific_category_budget_includes_only_matching_category(self):
        from expenses.models import Expense

        self._auth_owner()
        start_date = timezone.datetime(2026, 5, 1).date()
        end_date = timezone.datetime(2026, 5, 31).date()

        budget_food = Budget.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name='Food Budget',
            amount=Decimal('1000.00'),
            period='MONTHLY',
            category='FOOD',
            start_date=start_date,
            end_date=end_date,
        )

        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Approved Food',
            amount=Decimal('70.00'),
            category='FOOD',
            date=start_date,
            status='APPROVED',
        )
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Approved Transport',
            amount=Decimal('90.00'),
            category='TRANSPORT',
            date=end_date,
            status='APPROVED',
        )

        spent_amount = self._get_budget_spent_amount(budget_food.id)
        self.assertEqual(spent_amount, Decimal('70.00'))

    def test_date_range_inclusive_start_and_end(self):
        from expenses.models import Expense

        self._auth_owner()
        start_date = timezone.datetime(2026, 6, 10).date()
        end_date = timezone.datetime(2026, 6, 20).date()

        budget = Budget.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name='Inclusive Date Budget',
            amount=Decimal('1000.00'),
            period='MONTHLY',
            category='ALL',
            start_date=start_date,
            end_date=end_date,
        )

        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='On start date',
            amount=Decimal('10.00'),
            category='FOOD',
            date=start_date,
            status='APPROVED',
        )
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='On end date',
            amount=Decimal('20.00'),
            category='FOOD',
            date=end_date,
            status='APPROVED',
        )

        spent_amount = self._get_budget_spent_amount(budget.id)
        self.assertEqual(spent_amount, Decimal('30.00'))

    def test_date_range_excludes_outside_start_and_end(self):
        from expenses.models import Expense

        self._auth_owner()
        start_date = timezone.datetime(2026, 7, 1).date()
        end_date = timezone.datetime(2026, 7, 31).date()

        budget = Budget.objects.create(
            organization=self.organization,
            created_by=self.owner,
            name='Exclusive Date Budget',
            amount=Decimal('1000.00'),
            period='MONTHLY',
            category='ALL',
            start_date=start_date,
            end_date=end_date,
        )

        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Before start date',
            amount=Decimal('10.00'),
            category='FOOD',
            date=start_date - timedelta(days=1),
            status='APPROVED',
        )
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='After end date',
            amount=Decimal('20.00'),
            category='FOOD',
            date=end_date + timedelta(days=1),
            status='APPROVED',
        )

        spent_amount = self._get_budget_spent_amount(budget.id)
        self.assertEqual(spent_amount, Decimal('0'))
