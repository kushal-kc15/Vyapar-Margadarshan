from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from analytics.anomaly_notifications import notify_owners_if_expense_is_unusual
from expenses.models import Expense
from notifications.models import Notification
from organizations.models import Organization, OrganizationMember


User = get_user_model()


class UnusualExpenseNotificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username='anomalyowner', email='anomaly-owner@example.com', password='StrongPass123!')
        self.staff = User.objects.create_user(username='anomalystaff', email='anomaly-staff@example.com', password='StrongPass123!')
        self.organization = Organization.objects.create(name='Anomaly Notification Org')
        OrganizationMember.objects.create(user=self.owner, organization=self.organization, role='OWNER')
        OrganizationMember.objects.create(user=self.staff, organization=self.organization, role='STAFF')
        self.staff.active_organization = self.organization
        self.staff.save(update_fields=['active_organization'])

    def create_history(self, organization=None, user=None):
        organization = organization or self.organization
        user = user or self.owner
        for index, amount in enumerate(['95.00', '100.00', '105.00'], start=1):
            Expense.objects.create(
                organization=organization,
                user=user,
                title=f'Historical expense {index}',
                amount=Decimal(amount),
                category='FOOD',
                vendor='Cafe A',
                date=date.today() - timedelta(days=10 + index),
                status='APPROVED',
            )

    def submit_staff_expense(self, amount='500.00'):
        self.client.force_authenticate(self.staff)
        return self.client.post(
            '/api/expenses/',
            {
                'title': 'Team meal',
                'amount': amount,
                'category': 'FOOD',
                'vendor': 'Cafe A',
                'date': date.today().isoformat(),
                'description': 'Submitted for review',
            },
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

    def unusual_notifications(self):
        return Notification.objects.filter(notification_type='UNUSUAL_EXPENSE')

    def test_owner_receives_notification_for_high_staff_anomaly(self):
        self.create_history()

        response = self.submit_staff_expense()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        notification = self.unusual_notifications().get(user=self.owner)
        self.assertGreaterEqual(notification.metadata['anomaly_score'], 50)
        self.assertIn(notification.metadata['severity'], {'MEDIUM', 'HIGH'})
        self.assertTrue(notification.metadata['reasons'])
        self.assertEqual(notification.related_object_id, response.data['id'])

    def test_low_score_does_not_create_unusual_notification(self):
        self.create_history()

        response = self.submit_staff_expense(amount='110.00')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(self.unusual_notifications().exists())

    @patch('analytics.views.detect_expense_anomalies')
    def test_owner_created_expense_does_not_create_notification(self, detect):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            '/api/expenses/',
            {
                'title': 'Owner expense', 'amount': '900.00', 'category': 'FOOD',
                'vendor': 'Cafe A', 'date': date.today().isoformat(),
            },
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(self.unusual_notifications().exists())
        detect.assert_not_called()

    @patch('analytics.views.detect_expense_anomalies', side_effect=RuntimeError('scoring unavailable'))
    def test_scoring_failure_does_not_break_expense_creation(self, _detect):
        response = self.submit_staff_expense()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Expense.objects.get(id=response.data['id']).status, 'SUBMITTED')
        self.assertFalse(self.unusual_notifications().exists())

    def test_cross_workspace_history_is_not_used_for_scoring(self):
        other_owner = User.objects.create_user(username='otheranomalyowner', password='StrongPass123!')
        other_org = Organization.objects.create(name='Other Anomaly Org')
        OrganizationMember.objects.create(user=other_owner, organization=other_org, role='OWNER')
        self.create_history(organization=other_org, user=other_owner)

        response = self.submit_staff_expense()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(self.unusual_notifications().exists())

    def test_duplicate_owner_notification_is_prevented(self):
        self.create_history()
        response = self.submit_staff_expense()
        expense = Expense.objects.get(id=response.data['id'])

        notify_owners_if_expense_is_unusual(expense)

        self.assertEqual(self.unusual_notifications().filter(user=self.owner).count(), 1)
