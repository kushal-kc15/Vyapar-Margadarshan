from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from budgets.models import Budget, derive_budget_date_range
from expenses.models import Expense
from organizations.models import Organization, OrganizationMember


class Command(BaseCommand):
    help = 'Create idempotent Spending Health Check demo data for the college project workspace.'

    @transaction.atomic
    def handle(self, *args, **options):
        organization = Organization.objects.filter(name__iexact='college project').first()
        if not organization:
            raise CommandError('Organization "college project" was not found.')

        owner_membership = OrganizationMember.objects.filter(
            organization=organization,
            role='OWNER',
        ).select_related('user').first()
        staff_membership = OrganizationMember.objects.filter(
            organization=organization,
            role='STAFF',
        ).select_related('user').first()
        if not owner_membership:
            raise CommandError('The organization needs an existing owner member.')

        owner = owner_membership.user
        submitter = staff_membership.user if staff_membership else owner
        today = timezone.localdate()
        month_start = today.replace(day=1)
        _, month_end = derive_budget_date_range('MONTHLY', month_start)

        budget_specs = [
            ('Office Supplies Monthly Budget', 'OFFICE', Decimal('20000.00'), 80),
            ('Travel Budget', 'TRAVEL', Decimal('30000.00'), 80),
            ('[Health Demo] Utilities Budget', 'UTILITIES', Decimal('10000.00'), 80),
            ('[Health Demo] Marketing Budget', 'MARKETING', Decimal('7000.00'), 80),
        ]
        budgets_created = 0
        budgets_updated = 0
        for name, category, amount, threshold in budget_specs:
            budget, created = Budget.objects.get_or_create(
                organization=organization,
                name=name,
                defaults={
                    'created_by': owner,
                    'category': category,
                    'amount': amount,
                    'period': 'MONTHLY',
                    'alert_threshold': threshold,
                    'start_date': month_start,
                    'end_date': month_end,
                    'is_active': True,
                },
            )
            budget.category = category
            budget.amount = amount
            budget.period = 'MONTHLY'
            budget.alert_threshold = threshold
            budget.start_date = month_start
            budget.end_date = month_end
            budget.is_active = True
            budget.created_by = owner
            budget.save()
            budgets_created += int(created)
            budgets_updated += int(not created)

        approved_specs = [
            ('[Health Demo] Office storage cabinets', '11000.00', 'OFFICE', 'Kathmandu Office Mart', 'Storage cabinets for finance records', today),
            ('[Health Demo] Printer toner and supplies', '10000.00', 'OFFICE', 'New Road Business Supplies', 'Printer supplies for the administration team', today),
            ('[Health Demo] Stationery purchase', '4500.00', 'OFFICE', 'Pokhara Stationery Center', 'Monthly stationery purchase', today - timedelta(days=1)),
            ('[Health Demo] Pokhara field visit hotel', '12000.00', 'TRAVEL', 'Hotel Barahi Pokhara', 'Accommodation for the field visit', today),
            ('[Health Demo] Field visit transportation', '8500.00', 'TRAVEL', 'Greenline Travels', 'Transportation for the project field visit', today - timedelta(days=1)),
            ('[Health Demo] Field team travel allowance', '6000.00', 'TRAVEL', 'Field Operations Desk', 'Approved travel allowance for field staff', today),
            ('[Health Demo] Internet and connectivity', '9200.00', 'UTILITIES', 'WorldLink Communications', 'Monthly office internet and connectivity charge', today),
            ('[Health Demo] Local promotion campaign', '7600.00', 'MARKETING', 'Kathmandu Media House', 'Local promotion and printed campaign materials', today),
        ]
        pending_specs = [
            ('[Health Demo] Replacement network equipment', '22000.00', 'OTHER', 'Himalayan IT Solutions', 'Network equipment', today),
            ('[Health Demo] Office supplies without receipt', '9500.00', 'OFFICE', 'Putalisadak Office Traders', 'Office supplies for the administration desk', today),
            ('[Health Demo] Duplicate stationery claim', '4500.00', 'OFFICE', 'Pokhara Stationery Center', 'Stationery claim', today),
            ('[Health Demo] Unverified miscellaneous purchase', '7500.00', 'OTHER', 'Unknown Vendor', 'Supplies', today),
            ('[Health Demo] Older maintenance request', '8500.00', 'OTHER', 'Everest Repair Services', 'Repair work awaiting supporting documents', today - timedelta(days=10)),
        ]

        expenses_created = 0
        expenses_updated = 0
        for status, user, specs in (
            ('APPROVED', owner, approved_specs),
            ('PENDING', submitter, pending_specs),
        ):
            for title, amount, category, vendor, description, expense_date in specs:
                _, created = Expense.objects.update_or_create(
                    organization=organization,
                    title=title,
                    defaults={
                        'user': user,
                        'amount': Decimal(amount),
                        'category': category,
                        'vendor': vendor,
                        'date': expense_date,
                        'description': description,
                        'status': status,
                        'reviewed_by': owner if status == 'APPROVED' else None,
                        'reviewed_at': timezone.now() if status == 'APPROVED' else None,
                        'rejection_reason': '',
                    },
                )
                expenses_created += int(created)
                expenses_updated += int(not created)

        self.stdout.write(self.style.SUCCESS(f'Workspace: {organization.name} (id={organization.id})'))
        self.stdout.write(f'Budgets created: {budgets_created}; updated: {budgets_updated}')
        self.stdout.write(f'Expenses created: {expenses_created}; updated: {expenses_updated}')
        self.stdout.write('No users, members, organizations, or existing expenses were deleted.')
