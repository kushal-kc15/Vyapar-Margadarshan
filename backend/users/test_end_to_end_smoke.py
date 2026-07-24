from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from budgets.models import Budget
from organizations.models import Organization, OrganizationMember
from receipts.models import Receipt

User = get_user_model()


class EndToEndSmokeTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username='smokeowner',
            email='smoke-owner@example.com',
            password='StrongPass123!',
            email_verified=True,
        )
        self.staff = User.objects.create_user(
            username='smokestaff',
            email='smoke-staff@example.com',
            password='StrongPass123!',
            email_verified=True,
        )
        self.organization = Organization.objects.create(name='Smoke Org')
        OrganizationMember.objects.create(user=self.owner, organization=self.organization, role='OWNER')
        OrganizationMember.objects.create(user=self.staff, organization=self.organization, role='STAFF')
        self.owner.active_organization = self.organization
        self.owner.save(update_fields=['active_organization'])
        self.staff.active_organization = self.organization
        self.staff.save(update_fields=['active_organization'])
        self.budget = Budget.objects.create(
            organization=self.organization,
            name='Smoke Food Budget',
            amount=Decimal('1000.00'),
            period='MONTHLY',
            category='FOOD',
            start_date=date.today().replace(day=1),
            end_date=date.today() + timedelta(days=30),
            created_by=self.owner,
        )

    def authenticate_owner(self):
        self.client.force_authenticate(self.owner)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.organization.id))

    def authenticate_staff(self):
        self.client.force_authenticate(self.staff)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.organization.id))

    def test_core_business_flow_smoke(self):
        login_response = self.client.post(
            '/api/auth/login/',
            {'email': self.owner.email, 'password': 'StrongPass123!'},
            format='json',
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', login_response.data)

        self.authenticate_owner()
        owner_expense_response = self.client.post(
            '/api/expenses/',
            {
                'title': 'Owner lunch smoke',
                'amount': '125.50',
                'category': 'FOOD',
                'vendor': 'Smoke Cafe',
                'date': date.today().isoformat(),
                'description': 'Smoke test approved expense',
            },
            format='json',
        )
        self.assertEqual(owner_expense_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(owner_expense_response.data['status'], 'APPROVED')

        self.authenticate_staff()
        staff_expense_response = self.client.post(
            '/api/expenses/',
            {
                'title': 'Staff taxi smoke',
                'amount': '45.00',
                'category': 'TRANSPORT',
                'vendor': 'Smoke Taxi',
                'date': date.today().isoformat(),
                'description': 'Smoke test pending expense',
            },
            format='json',
        )
        self.assertEqual(staff_expense_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(staff_expense_response.data['status'], 'SUBMITTED')

        self.authenticate_owner()
        pending_response = self.client.get('/api/expenses/pending_approvals/')
        self.assertEqual(pending_response.status_code, status.HTTP_200_OK)
        pending_ids = [expense['id'] for expense in pending_response.data]
        self.assertIn(staff_expense_response.data['id'], pending_ids)

        approve_response = self.client.post(f"/api/expenses/{staff_expense_response.data['id']}/approve/")
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(approve_response.data['status'], 'APPROVED')

        dashboard_response = self.client.get('/api/expenses/dashboard_metrics/')
        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(dashboard_response.data['month']['count'], 2)

        analytics_response = self.client.get('/api/analytics/overview/')
        self.assertEqual(analytics_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(analytics_response.data['transaction_count'], 2)

        anomaly_response = self.client.get('/api/analytics/anomalies/')
        self.assertEqual(anomaly_response.status_code, status.HTTP_200_OK)
        self.assertIn('anomalies', anomaly_response.data)

        receipt = Receipt.objects.create(
            organization=self.organization,
            user=self.owner,
            image='receipts/smoke.gif',
            status='COMPLETED',
            processed_at=timezone.now(),
        )
        verify_response = self.client.post(
            f'/api/receipts/{receipt.id}/verify/',
            {
                'vendor_name': 'Smoke Receipt Vendor',
                'total_amount': '55.25',
                'receipt_date': date.today().isoformat(),
                'category': 'FOOD',
                'description': 'Verified smoke receipt',
                'line_items': [],
            },
            format='json',
        )
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        self.assertEqual(verify_response.data['status'], 'VERIFIED')

        receipt_expense_response = self.client.post(f'/api/receipts/{receipt.id}/create_expense/')
        self.assertEqual(receipt_expense_response.status_code, status.HTTP_201_CREATED)
        self.assertIn('expense_id', receipt_expense_response.data)

        reports_response = self.client.get('/api/analytics/budget-burn-rate/')
        self.assertEqual(reports_response.status_code, status.HTTP_200_OK)
        self.assertIn('budgets', reports_response.data)
