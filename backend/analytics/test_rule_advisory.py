from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from budgets.models import Budget
from expenses.models import Expense
from organizations.models import Organization, OrganizationMember


User = get_user_model()


class RuleBasedAdviceEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username='ruleowner', email='ruleowner@example.com', password='StrongPass123!')
        self.staff = User.objects.create_user(username='rulestaff', email='rulestaff@example.com', password='StrongPass123!')
        self.other_owner = User.objects.create_user(username='other-ruleowner', email='other-ruleowner@example.com', password='StrongPass123!')
        self.organization = Organization.objects.create(name='Rule Advice Org')
        self.other_organization = Organization.objects.create(name='Other Rule Advice Org')
        OrganizationMember.objects.create(user=self.owner, organization=self.organization, role='OWNER')
        OrganizationMember.objects.create(user=self.staff, organization=self.organization, role='STAFF')
        OrganizationMember.objects.create(user=self.other_owner, organization=self.other_organization, role='OWNER')
        self.owner.active_organization = self.organization
        self.owner.save(update_fields=['active_organization'])
        self.staff.active_organization = self.organization
        self.staff.save(update_fields=['active_organization'])
        self.start = date.today().replace(day=1)
        self.end = date.today()

    @property
    def url(self):
        return f'/api/analytics/rule-based-advice/?start_date={self.start}&end_date={self.end}'

    def expense(self, *, amount, category='FOOD', vendor='Cafe A', status_value='APPROVED', user=None, organization=None, expense_date=None):
        return Expense.objects.create(
            organization=organization or self.organization,
            user=user or self.owner,
            title=f'{category} expense',
            amount=Decimal(amount),
            category=category,
            vendor=vendor,
            date=expense_date or self.end,
            status=status_value,
        )

    def authenticate(self, user=None):
        self.client.force_authenticate(user or self.owner)

    def codes(self, response):
        return {item['code'] for item in response.data['advisories']}

    def test_endpoint_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_approved_expenses_returns_info_advisory(self):
        self.expense(amount='900', status_value='PENDING')
        self.expense(amount='800', status_value='REJECTED')
        self.authenticate()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary']['approved_count'], 0)
        self.assertIn('NO_APPROVED_EXPENSES', self.codes(response))

    def test_only_active_workspace_data_is_used(self):
        self.expense(amount='25')
        self.expense(amount='999', organization=self.other_organization, user=self.other_owner, category='OTHER', vendor='Other Vendor')
        self.authenticate()
        response = self.client.get(self.url)
        self.assertEqual(response.data['summary']['approved_total'], '25.00')
        self.assertEqual(response.data['organization_id'], self.organization.id)

    def test_budget_exceeded_and_near_limit_rules(self):
        self.expense(amount='180', category='FOOD')
        self.expense(amount='80', category='TRAVEL', vendor='Travel Co')
        Budget.objects.create(organization=self.organization, name='Food Limit', amount='150', period='MONTHLY', category='FOOD', alert_threshold=80, start_date=self.start, end_date=self.end, created_by=self.owner)
        Budget.objects.create(organization=self.organization, name='Travel Limit', amount='100', period='MONTHLY', category='TRAVEL', alert_threshold=75, start_date=self.start, end_date=self.end, created_by=self.owner)
        self.authenticate()
        response = self.client.get(self.url)
        self.assertIn('BUDGET_EXCEEDED', self.codes(response))
        self.assertIn('BUDGET_NEAR_LIMIT', self.codes(response))

    def test_category_and_vendor_concentration_rules(self):
        self.expense(amount='60', category='FOOD', vendor='Main Vendor')
        self.expense(amount='25', category='FOOD', vendor='Main Vendor')
        self.expense(amount='15', category='TRAVEL', vendor='Other Vendor')
        self.authenticate()
        response = self.client.get(self.url)
        self.assertIn('CATEGORY_CONCENTRATION', self.codes(response))
        self.assertIn('VENDOR_CONCENTRATION', self.codes(response))

    def test_monthly_spend_increase_rule_uses_previous_comparable_period(self):
        period_days = (self.end - self.start).days + 1
        previous_end = self.start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=period_days - 1)
        self.expense(amount='150', expense_date=self.end)
        self.expense(amount='100', expense_date=previous_start)
        self.authenticate()
        response = self.client.get(self.url)
        self.assertIn('MONTHLY_SPEND_INCREASE', self.codes(response))

    def test_staff_scope_uses_only_staff_approved_expenses(self):
        self.expense(amount='500', user=self.owner)
        self.expense(amount='40', user=self.staff, category='TRAVEL', vendor='Staff Vendor')
        self.authenticate(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.data['scope'], 'personal')
        self.assertEqual(response.data['summary']['approved_total'], '40.00')
        self.assertEqual(response.data['summary']['approved_count'], 1)

    def test_pending_and_rejected_expenses_are_excluded(self):
        self.expense(amount='30')
        self.expense(amount='400', status_value='PENDING')
        self.expense(amount='500', status_value='REJECTED')
        self.authenticate()
        response = self.client.get(self.url)
        self.assertEqual(response.data['summary']['approved_total'], '30.00')
        self.assertEqual(response.data['summary']['approved_count'], 1)
