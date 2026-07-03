import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from analytics.ai_insights import AIInsightError
from budgets.models import Budget
from expenses.models import Expense
from organizations.models import Organization, OrganizationMember

User = get_user_model()


class AnalyticsEndpointTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username='analyticsowner',
            email='analytics-owner@example.com',
            password='StrongPass123!',
            email_verified=True,
        )
        self.staff = User.objects.create_user(
            username='analyticsstaff',
            email='analytics-staff@example.com',
            password='StrongPass123!',
            email_verified=True,
        )
        self.other_owner = User.objects.create_user(
            username='analyticsother',
            email='analytics-other@example.com',
            password='StrongPass123!',
            email_verified=True,
        )
        self.organization = Organization.objects.create(name='Analytics Org')
        self.other_organization = Organization.objects.create(name='Other Analytics Org')
        OrganizationMember.objects.create(user=self.owner, organization=self.organization, role='OWNER')
        OrganizationMember.objects.create(user=self.staff, organization=self.organization, role='STAFF')
        OrganizationMember.objects.create(user=self.other_owner, organization=self.other_organization, role='OWNER')
        self.owner.active_organization = self.organization
        self.owner.save(update_fields=['active_organization'])
        self.staff.active_organization = self.organization
        self.staff.save(update_fields=['active_organization'])
        self.other_owner.active_organization = self.other_organization
        self.other_owner.save(update_fields=['active_organization'])

        today = date.today()
        self.owner_food = Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Owner lunch',
            amount=Decimal('100.00'),
            category='FOOD',
            vendor='Cafe A',
            date=today,
            status='APPROVED',
        )
        self.staff_transport = Expense.objects.create(
            organization=self.organization,
            user=self.staff,
            title='Staff taxi',
            amount=Decimal('50.00'),
            category='TRANSPORT',
            vendor='Taxi Co',
            date=today,
            status='APPROVED',
        )
        Expense.objects.create(
            organization=self.organization,
            user=self.staff,
            title='Pending staff meal',
            amount=Decimal('25.00'),
            category='FOOD',
            vendor='Cafe A',
            date=today,
            status='PENDING',
        )
        Expense.objects.create(
            organization=self.other_organization,
            user=self.other_owner,
            title='Other org expense',
            amount=Decimal('900.00'),
            category='OTHER',
            vendor='Other Vendor',
            date=today,
            status='APPROVED',
        )
        self.budget = Budget.objects.create(
            organization=self.organization,
            name='Food Budget',
            amount=Decimal('300.00'),
            period='MONTHLY',
            category='FOOD',
            start_date=today.replace(day=1),
            end_date=today + timedelta(days=30),
            created_by=self.owner,
        )

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def test_owner_category_breakdown_uses_org_approved_expenses_only(self):
        self.authenticate(self.owner)

        response = self.client.get('/api/analytics/category-breakdown/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['scope'], 'organization')
        self.assertEqual(response.data['total_amount'], 150.0)
        categories = {item['category']: item for item in response.data['breakdown']}
        self.assertEqual(categories['FOOD']['total'], 100.0)
        self.assertEqual(categories['TRANSPORT']['total'], 50.0)
        self.assertNotIn('OTHER', categories)

    def test_staff_analytics_scope_is_personal_approved_spend(self):
        self.authenticate(self.staff)

        response = self.client.get('/api/analytics/overview/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['scope'], 'personal')
        self.assertEqual(response.data['total_spent'], 50.0)
        self.assertEqual(response.data['transaction_count'], 1)

    def test_report_detail_owner_is_org_wide_approved_only(self):
        Expense.objects.create(
            organization=self.organization,
            user=self.staff,
            title='Rejected report detail',
            amount=Decimal('35.00'),
            category='OTHER',
            vendor='Rejected Vendor',
            date=date.today(),
            status='REJECTED',
        )
        self.authenticate(self.owner)

        response = self.client.get('/api/analytics/report-detail/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['scope'], 'organization')
        self.assertEqual(response.data['summary']['total'], 150.0)
        self.assertEqual(response.data['summary']['count'], 2)
        titles = {row['title'] for row in response.data['expenses']}
        self.assertEqual(titles, {'Owner lunch', 'Staff taxi'})
        self.assertEqual(response.data['top_category']['category'], 'FOOD')
        self.assertEqual(response.data['top_vendor']['vendor'], 'Cafe A')

    def test_report_detail_staff_is_own_approved_only(self):
        self.authenticate(self.staff)

        response = self.client.get('/api/analytics/report-detail/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['scope'], 'personal')
        self.assertEqual(response.data['summary']['total'], 50.0)
        self.assertEqual(response.data['summary']['count'], 1)
        self.assertEqual(response.data['expenses'][0]['title'], 'Staff taxi')
        self.assertEqual(response.data['expenses'][0]['user_id'], self.staff.id)

    def test_report_detail_excludes_cross_org_data(self):
        self.authenticate(self.other_owner)

        response = self.client.get('/api/analytics/report-detail/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['organization_id'], self.other_organization.id)
        self.assertEqual(response.data['summary']['total'], 900.0)
        self.assertEqual(response.data['summary']['count'], 1)
        self.assertEqual(response.data['expenses'][0]['title'], 'Other org expense')

    def test_report_detail_applies_category_vendor_and_date_filters(self):
        today = date.today().isoformat()
        self.authenticate(self.owner)

        response = self.client.get(
            f'/api/analytics/report-detail/?start_date={today}&end_date={today}&category=TRANSPORT&vendor=Taxi'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary']['total'], 50.0)
        self.assertEqual(response.data['summary']['count'], 1)
        self.assertEqual(response.data['filters']['category'], 'TRANSPORT')
        self.assertEqual(response.data['filters']['vendor'], 'Taxi')
        self.assertEqual(response.data['expenses'][0]['title'], 'Staff taxi')

    def test_spending_trends_validates_period_and_date_range(self):
        self.authenticate(self.owner)

        bad_period = self.client.get('/api/analytics/spending-trends/?period=hourly')
        self.assertEqual(bad_period.status_code, status.HTTP_400_BAD_REQUEST)

        bad_range = self.client.get('/api/analytics/spending-trends/?start_date=2026-02-01&end_date=2026-01-01')
        self.assertEqual(bad_range.status_code, status.HTTP_400_BAD_REQUEST)

    def test_report_detail_daily_trend_includes_end_date(self):
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Current day expense',
            amount=Decimal('252.00'),
            category='OTHER',
            date=date(2026, 7, 3),
            status='APPROVED',
        )
        self.authenticate(self.owner)

        response = self.client.get(
            '/api/analytics/report-detail/?start_date=2026-07-01&end_date=2026-07-03&period=daily'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        july_third = next(
            row for row in response.data['trends']
            if row['period_start'] == date(2026, 7, 3)
        )
        self.assertGreaterEqual(july_third['total'], 252.0)
        self.assertIn('Current day expense', {row['title'] for row in response.data['expenses']})

    def test_vendor_summary_limits_and_sorts_vendors(self):
        self.authenticate(self.owner)

        response = self.client.get('/api/analytics/vendor-summary/?limit=1')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['vendors']), 1)
        self.assertEqual(response.data['vendors'][0]['vendor'], 'Cafe A')
        self.assertEqual(response.data['vendors'][0]['total'], 100.0)

    def export_rows(self, user, query=''):
        self.authenticate(user)
        response = self.client.get(f'/api/analytics/export-csv/{query}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode('utf-8-sig')
        return response, list(csv.reader(io.StringIO(content))), content

    def test_export_csv_returns_business_report_sections(self):
        response, rows, content = self.export_rows(self.owner)

        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment; filename="approved-expense-report_', response['Content-Disposition'])
        self.assertEqual(rows[0], ['Vyapar Margadarshan Approved Expense Report'])
        self.assertIn(['Data scope', 'Approved expenses only'], rows)
        self.assertIn(['Category Breakdown'], rows)
        self.assertIn(['Vendor Summary'], rows)
        self.assertIn(['Spending Trend'], rows)
        self.assertIn('Approved expenses only', content)

    def test_owner_export_includes_only_organization_approved_expenses(self):
        Expense.objects.create(
            organization=self.organization,
            user=self.staff,
            title='Pending export expense',
            amount=Decimal('45.00'),
            category='OTHER',
            vendor='Pending Vendor',
            date=date.today(),
            status='PENDING',
        )
        Expense.objects.create(
            organization=self.organization,
            user=self.staff,
            title='Rejected expense',
            amount=Decimal('35.00'),
            category='OTHER',
            vendor='Rejected Vendor',
            date=date.today(),
            status='REJECTED',
        )

        _, rows, content = self.export_rows(self.owner)

        self.assertIn(['Approved amount', '150.00'], rows)
        self.assertIn(['Total approved expenses', '2'], rows)
        self.assertIn('Cafe A', content)
        self.assertIn('Taxi Co', content)
        self.assertNotIn('Pending Vendor', content)
        self.assertNotIn('Rejected Vendor', content)
        self.assertNotIn('Other Vendor', content)

    def test_staff_export_contains_only_their_approved_expenses(self):
        _, rows, content = self.export_rows(self.staff)

        self.assertIn(['Approved amount', '50.00'], rows)
        self.assertIn(['Total approved expenses', '1'], rows)
        self.assertIn('Taxi Co', content)
        self.assertNotIn('Cafe A', content)
        self.assertNotIn('Other Vendor', content)

    def test_export_csv_applies_date_range_and_period(self):
        yesterday = date.today() - timedelta(days=1)
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Old approved expense',
            amount=Decimal('70.00'),
            category='OFFICE',
            vendor='Old Vendor',
            date=yesterday,
            status='APPROVED',
        )
        today = date.today().isoformat()

        _, rows, content = self.export_rows(
            self.owner,
            f'?start_date={today}&end_date={today}&period=monthly',
        )

        self.assertIn(['Date range', f'{today} to {today}'], rows)
        self.assertIn(['Approved amount', '150.00'], rows)
        self.assertNotIn('Old Vendor', content)
        trend_header_index = rows.index(['Period', 'Period start', 'Total spend', 'Count'])
        self.assertEqual(rows[trend_header_index + 1][0], date.today().strftime('%b %Y'))
        self.assertEqual(rows[trend_header_index + 1][1], date.today().replace(day=1).isoformat())

    def test_export_csv_applies_category_vendor_filters_and_included_expenses(self):
        self.authenticate(self.owner)

        response = self.client.get('/api/analytics/export-csv/?category=TRANSPORT&vendor=Taxi')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode('utf-8-sig')
        rows = list(csv.reader(io.StringIO(content)))
        self.assertIn(['Category filter', 'Transportation'], rows)
        self.assertIn(['Vendor filter', 'Taxi'], rows)
        self.assertIn(['Approved amount', '50.00'], rows)
        self.assertIn(['Approved Expenses Included'], rows)
        self.assertIn('Staff taxi', content)
        self.assertNotIn('Owner lunch', content)

    def test_export_csv_protects_formula_like_text(self):
        Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Formula vendor expense',
            amount=Decimal('10.00'),
            category='OTHER',
            vendor='=SUM(A1:A2)',
            date=date.today(),
            status='APPROVED',
        )

        _, rows, content = self.export_rows(self.owner)

        self.assertIn(["'=SUM(A1:A2)", '1', '10.00'], rows)
        self.assertNotIn('\n=SUM(A1:A2),', content)

    def test_export_csv_validates_period_and_date_range(self):
        self.authenticate(self.owner)

        bad_period = self.client.get('/api/analytics/export-csv/?period=hourly')
        bad_range = self.client.get(
            '/api/analytics/export-csv/?start_date=2026-02-01&end_date=2026-01-01'
        )

        self.assertEqual(bad_period.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(bad_range.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_pdf_requires_authentication(self):
        response = self.client.get('/api/analytics/export-pdf/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_export_pdf_returns_downloadable_pdf(self):
        self.authenticate(self.owner)

        response = self.client.get('/api/analytics/export-pdf/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('Vyapar_Margadarshan_Report_', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_export_pdf_uses_active_workspace_and_approved_only(self):
        Expense.objects.create(
            organization=self.organization,
            user=self.staff,
            title='Pending PDF expense',
            amount=Decimal('999.00'),
            category='OTHER',
            date=date.today(),
            status='PENDING',
        )
        Expense.objects.create(
            organization=self.organization,
            user=self.staff,
            title='Rejected PDF expense',
            amount=Decimal('888.00'),
            category='OTHER',
            date=date.today(),
            status='REJECTED',
        )
        self.authenticate(self.owner)

        with patch('analytics.views.build_expense_report_pdf', return_value=b'%PDF-mock') as build_pdf:
            response = self.client.get('/api/analytics/export-pdf/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        queryset = build_pdf.call_args.kwargs['expenses']
        titles = set(queryset.values_list('title', flat=True))
        self.assertEqual(titles, {'Owner lunch', 'Staff taxi'})
        self.assertNotIn('Other org expense', titles)
        self.assertNotIn('Pending PDF expense', titles)
        self.assertNotIn('Rejected PDF expense', titles)

    def test_export_pdf_applies_report_filters(self):
        today = date.today().isoformat()
        self.authenticate(self.owner)

        with patch('analytics.views.build_expense_report_pdf', return_value=b'%PDF-mock') as build_pdf:
            response = self.client.get(
                f'/api/analytics/export-pdf/?start_date={today}&end_date={today}'
                '&category=TRANSPORT&vendor=Taxi&period=daily'
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        call = build_pdf.call_args.kwargs
        self.assertEqual(list(call['expenses'].values_list('title', flat=True)), ['Staff taxi'])
        self.assertEqual(call['start_date'], date.today())
        self.assertEqual(call['end_date'], date.today())
        self.assertEqual(call['category'], 'TRANSPORT')
        self.assertEqual(call['vendor'], 'Taxi')

    def test_budget_burn_rate_returns_projection_data(self):
        self.authenticate(self.owner)

        response = self.client.get('/api/analytics/budget-burn-rate/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['budgets']), 1)
        budget = response.data['budgets'][0]
        self.assertEqual(budget['budget_id'], self.budget.id)
        self.assertEqual(budget['spent_amount'], 100.0)
        self.assertEqual(budget['budget_amount'], 300.0)
        self.assertIn('projected_spend', budget)
        self.assertIn('is_projected_over_budget', budget)

    def test_ai_insights_returns_provider_summary(self):
        self.authenticate(self.owner)
        provider_summary = {
            'summary': 'Food is the main month-to-date driver.',
            'insights': ['Food totals 100.0 this month.'],
            'warnings': ['Food is a concentrated category.'],
            'recommendations': ['Review food vendors before month close.'],
            'provider': 'gemini',
            'model': 'gemini-2.5-flash',
        }

        with patch('analytics.views.generate_ai_insight', return_value=provider_summary) as generate:
            response = self.client.get('/api/analytics/ai-insights/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['generated_by_ai'])
        self.assertEqual(response.data['summary'], provider_summary['summary'])
        self.assertEqual(response.data['provider'], 'gemini')
        self.assertEqual(response.data['period'], 'this_month')
        self.assertIn('snapshot_metrics', response.data)
        snapshot = generate.call_args.args[0]
        self.assertEqual(snapshot['scope'], 'organization')
        self.assertEqual(snapshot['expense_count'], 2)
        self.assertEqual(snapshot['total_approved_amount'], 150.0)
        self.assertIn('top_categories', snapshot)
        self.assertIn('highest_expenses', snapshot)

    def test_ai_insights_falls_back_when_provider_fails(self):
        self.authenticate(self.owner)

        with patch('analytics.views.generate_ai_insight', side_effect=AIInsightError('provider down')):
            response = self.client.get('/api/analytics/ai-insights/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['generated_by_ai'])
        self.assertEqual(response.data['provider'], 'fallback')
        self.assertEqual(response.data['source'], 'fallback')
        self.assertTrue(response.data['summary'])
        self.assertEqual(response.data['observations'], response.data['insights'])
        self.assertEqual(response.data['suggestions'], response.data['recommendations'])
        self.assertGreaterEqual(len(response.data['recommendations']), 1)

    def test_ai_insights_falls_back_on_unexpected_provider_error(self):
        self.authenticate(self.owner)

        with patch('analytics.views.generate_ai_insight', side_effect=RuntimeError('unexpected failure')):
            response = self.client.get('/api/analytics/ai-insights/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['source'], 'fallback')
        self.assertTrue(response.data['summary'])

    def test_staff_ai_insights_uses_only_own_approved_expenses(self):
        self.authenticate(self.staff)

        with patch('analytics.views.generate_ai_insight', side_effect=AIInsightError('provider down')):
            response = self.client.get('/api/analytics/ai-insights/?period=last_3_months')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['scope'], 'personal')
        self.assertEqual(response.data['snapshot_metrics']['expense_count'], 1)
        self.assertEqual(response.data['snapshot_metrics']['total_approved_amount'], 50.0)
        self.assertNotIn('100.0', response.data['summary'])

    def test_ai_insights_empty_period_skips_provider(self):
        self.authenticate(self.owner)

        with patch('analytics.views.generate_ai_insight') as generate:
            response = self.client.get('/api/analytics/ai-insights/?period=last_month')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['enough_data'])
        self.assertEqual(response.data['insights'], [])
        self.assertEqual(response.data['source'], 'none')
        self.assertEqual(
            response.data['summary'],
            'No approved spending data is available for the selected period.',
        )
        generate.assert_not_called()

    def test_ai_insights_rejects_unknown_period(self):
        self.authenticate(self.owner)

        response = self.client.get('/api/analytics/ai-insights/?period=yearly')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anomalies_flags_high_amount_and_duplicate_candidates(self):
        today = date.today()
        for index, amount in enumerate(['95.00', '100.00', '105.00'], start=1):
            Expense.objects.create(
                organization=self.organization,
                user=self.owner,
                title=f'Historical meal {index}',
                amount=Decimal(amount),
                category='FOOD',
                vendor='Cafe A',
                date=today - timedelta(days=10 + index),
                status='APPROVED',
            )
        high_expense = Expense.objects.create(
            organization=self.organization,
            user=self.staff,
            title='Suspicious team dinner',
            amount=Decimal('500.00'),
            category='FOOD',
            vendor='Cafe A',
            date=today,
            status='PENDING',
        )
        duplicate = Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Duplicate team dinner',
            amount=Decimal('500.00'),
            category='FOOD',
            vendor='Cafe A',
            date=today,
            status='APPROVED',
        )

        self.authenticate(self.owner)
        response = self.client.get('/api/analytics/anomalies/?amount_multiplier=2&minimum_baseline_count=3&limit=10')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        anomalies = {item['expense_id']: item for item in response.data['anomalies']}
        self.assertIn(high_expense.id, anomalies)
        self.assertNotIn(duplicate.id, anomalies)
        self.assertTrue(all(item['status'] == 'PENDING' for item in anomalies.values()))
        reason_codes = {reason['code'] for reason in anomalies[high_expense.id]['reasons']}
        self.assertIn('HIGH_CATEGORY_AMOUNT', reason_codes)
        self.assertIn('HIGH_VENDOR_AMOUNT', reason_codes)
        self.assertIn('DUPLICATE_CANDIDATE', reason_codes)
        duplicate_reason = next(reason for reason in anomalies[high_expense.id]['reasons'] if reason['code'] == 'DUPLICATE_CANDIDATE')
        self.assertIn(duplicate.id, duplicate_reason['matching_expense_ids'])

    def test_staff_anomalies_scope_to_own_expenses(self):
        today = date.today()
        for index in range(3):
            Expense.objects.create(
                organization=self.organization,
                user=self.owner,
                title=f'Owner baseline {index}',
                amount=Decimal('100.00'),
                category='OFFICE',
                vendor='Office Vendor',
                date=today - timedelta(days=20 + index),
                status='APPROVED',
            )
        owner_anomaly = Expense.objects.create(
            organization=self.organization,
            user=self.owner,
            title='Owner large office buy',
            amount=Decimal('600.00'),
            category='OFFICE',
            vendor='Office Vendor',
            date=today,
            status='PENDING',
        )

        self.authenticate(self.staff)
        response = self.client.get('/api/analytics/anomalies/?amount_multiplier=2&minimum_baseline_count=3')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['scope'], 'personal')
        flagged_ids = {item['expense_id'] for item in response.data['anomalies']}
        self.assertNotIn(owner_anomaly.id, flagged_ids)

    def test_anomalies_validate_query_params(self):
        self.authenticate(self.owner)

        bad_multiplier = self.client.get('/api/analytics/anomalies/?amount_multiplier=1')
        self.assertEqual(bad_multiplier.status_code, status.HTTP_400_BAD_REQUEST)

        bad_limit = self.client.get('/api/analytics/anomalies/?limit=0')
        self.assertEqual(bad_limit.status_code, status.HTTP_400_BAD_REQUEST)
