"""Seed the BusinessRule table from the static rule knowledge base."""
from django.core.management.base import BaseCommand

from analytics.models import BusinessRule
from analytics.rule_knowledge_base import EXPENSE_REVIEW_RULES


class Command(BaseCommand):
    help = 'Populate BusinessRule table from the static knowledge base (creates or updates).'

    def handle(self, *args, **options):
        created = 0
        updated = 0

        for code, rule_def in EXPENSE_REVIEW_RULES.items():
            defaults = {
                'name': rule_def['name'],
                'category': rule_def['category'],
                'description': rule_def['description'],
                'score': rule_def['score'],
                'severity': rule_def['severity'],
                'recommendation': rule_def['recommendation'],
                'threshold': {k: rule_def[k] for k in ('threshold',) if k in rule_def},
                'enabled': rule_def.get('enabled', True),
                'version': rule_def.get('version', '1.0'),
            }
            _, was_created = BusinessRule.objects.update_or_create(
                code=code,
                defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done. {created} created, {updated} updated. '
            f'{BusinessRule.objects.count()} total rules in database.'
        ))
