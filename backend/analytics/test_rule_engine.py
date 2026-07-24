"""Unit tests for the rule engine and knowledge base."""
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase

from analytics.rule_engine import evaluate_expense, risk_level_from_score, review_suggestion
from analytics.rule_knowledge_base import EXPENSE_REVIEW_RULES


class RiskLevelTests(TestCase):
    def test_low_range(self):
        self.assertEqual(risk_level_from_score(0), 'LOW')
        self.assertEqual(risk_level_from_score(30), 'LOW')

    def test_medium_range(self):
        self.assertEqual(risk_level_from_score(31), 'MEDIUM')
        self.assertEqual(risk_level_from_score(65), 'MEDIUM')

    def test_high_range(self):
        self.assertEqual(risk_level_from_score(66), 'HIGH')
        self.assertEqual(risk_level_from_score(100), 'HIGH')


class KnowledgeBaseTests(TestCase):
    def test_all_rules_have_required_fields(self):
        required = {'name', 'category', 'description', 'score', 'severity',
                    'recommendation', 'enabled', 'version'}
        for code, rule in EXPENSE_REVIEW_RULES.items():
            missing = required - set(rule.keys())
            self.assertFalse(missing, f'Rule {code} missing fields: {missing}')

    def test_all_scores_are_positive(self):
        for code, rule in EXPENSE_REVIEW_RULES.items():
            self.assertGreater(rule['score'], 0, f'Rule {code} has non-positive score')

    def test_all_severities_valid(self):
        valid = {'LOW', 'MEDIUM', 'HIGH'}
        for code, rule in EXPENSE_REVIEW_RULES.items():
            self.assertIn(rule['severity'], valid, f'Rule {code} has invalid severity')


def _make_expense(**kwargs):
    defaults = {
        'id': 1,
        'amount': Decimal('5000'),
        'category': 'OFFICE',
        'vendor': 'Test Vendor',
        'date': None,
        'description': 'Purchase of office supplies for quarterly needs',
        'status': 'PENDING',
        'organization': SimpleNamespace(id=1),
        'user_id': 1,
        'user': SimpleNamespace(get_full_name=lambda: 'Test User', username='testuser'),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _base_context(**overrides):
    defaults = {
        'amount_multiplier': Decimal('2.5'),
        'category_stats': None,
        'vendor_stats': None,
        'statistical_baseline': None,
        'duplicate_candidates': None,
        'is_new_vendor': False,
        'has_receipt': True,
        'budget_percentage': 0,
        'pending_days': 0,
    }
    defaults.update(overrides)
    return defaults


class MissingReceiptRuleTests(TestCase):
    def test_triggers_when_no_receipt(self):
        expense = _make_expense()
        context = _base_context(has_receipt=False)
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertIn('MISSING_RECEIPT', codes)
        self.assertGreaterEqual(result['risk_score'], 20)

    def test_does_not_trigger_when_receipt_exists(self):
        expense = _make_expense()
        context = _base_context(has_receipt=True)
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertNotIn('MISSING_RECEIPT', codes)


class MissingVendorRuleTests(TestCase):
    def test_triggers_when_vendor_empty(self):
        expense = _make_expense(vendor='')
        context = _base_context()
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertIn('MISSING_VENDOR', codes)

    def test_triggers_when_vendor_unknown(self):
        expense = _make_expense(vendor='unknown')
        context = _base_context()
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertIn('MISSING_VENDOR', codes)

    def test_does_not_trigger_when_vendor_present(self):
        expense = _make_expense(vendor='Office Depot')
        context = _base_context()
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertNotIn('MISSING_VENDOR', codes)


class NewVendorRuleTests(TestCase):
    def test_triggers_when_new_vendor(self):
        expense = _make_expense(vendor='Brand New Vendor')
        context = _base_context(is_new_vendor=True)
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertIn('NEW_VENDOR', codes)


class HighAmountRuleTests(TestCase):
    def test_critical_threshold(self):
        expense = _make_expense(amount=Decimal('30000'))
        context = _base_context()
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertIn('HIGH_AMOUNT_CRITICAL', codes)
        self.assertNotIn('HIGH_AMOUNT_ELEVATED', codes)

    def test_elevated_threshold(self):
        expense = _make_expense(amount=Decimal('15000'))
        context = _base_context()
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertIn('HIGH_AMOUNT_ELEVATED', codes)
        self.assertNotIn('HIGH_AMOUNT_CRITICAL', codes)

    def test_routine_threshold(self):
        expense = _make_expense(amount=Decimal('6000'))
        context = _base_context()
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertIn('HIGH_AMOUNT_ROUTINE', codes)

    def test_skipped_when_category_baseline_exists(self):
        expense = _make_expense(amount=Decimal('30000'))
        context = _base_context(category_stats={'avg': 25000, 'count': 5})
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertNotIn('HIGH_AMOUNT_CRITICAL', codes)


class HighCategoryAmountRuleTests(TestCase):
    def test_triggers_when_ratio_exceeds_multiplier(self):
        expense = _make_expense(amount=Decimal('10000'))
        context = _base_context(category_stats={'avg': 3000, 'count': 5})
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertIn('HIGH_CATEGORY_AMOUNT', codes)

    def test_does_not_trigger_when_amount_normal(self):
        expense = _make_expense(amount=Decimal('5000'))
        context = _base_context(category_stats={'avg': 4000, 'count': 5})
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertNotIn('HIGH_CATEGORY_AMOUNT', codes)


class DuplicateCandidateRuleTests(TestCase):
    def test_triggers_when_duplicates_found(self):
        dup = SimpleNamespace(id=99)
        expense = _make_expense()
        context = _base_context(duplicate_candidates=[dup])
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertIn('DUPLICATE_CANDIDATE', codes)

    def test_does_not_trigger_when_no_duplicates(self):
        expense = _make_expense()
        context = _base_context(duplicate_candidates=[])
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertNotIn('DUPLICATE_CANDIDATE', codes)


class BudgetRuleTests(TestCase):
    def test_exceeded_triggers_at_100_percent(self):
        expense = _make_expense()
        context = _base_context(budget_percentage=105.0)
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertIn('BUDGET_EXCEEDED', codes)
        self.assertNotIn('BUDGET_PRESSURE', codes)

    def test_pressure_triggers_at_80_percent(self):
        expense = _make_expense()
        context = _base_context(budget_percentage=85.0)
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertIn('BUDGET_PRESSURE', codes)
        self.assertNotIn('BUDGET_EXCEEDED', codes)

    def test_no_trigger_below_80(self):
        expense = _make_expense()
        context = _base_context(budget_percentage=50.0)
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertNotIn('BUDGET_EXCEEDED', codes)
        self.assertNotIn('BUDGET_PRESSURE', codes)


class WeakDescriptionRuleTests(TestCase):
    def test_triggers_when_description_short(self):
        expense = _make_expense(description='short')
        context = _base_context()
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertIn('WEAK_DESCRIPTION', codes)

    def test_does_not_trigger_when_description_adequate(self):
        expense = _make_expense(description='Purchase of office chairs for the team')
        context = _base_context()
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertNotIn('WEAK_DESCRIPTION', codes)


class OldPendingExpenseRuleTests(TestCase):
    def test_triggers_when_pending_over_7_days(self):
        expense = _make_expense()
        context = _base_context(pending_days=10)
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertIn('OLD_PENDING_EXPENSE', codes)

    def test_does_not_trigger_within_threshold(self):
        expense = _make_expense()
        context = _base_context(pending_days=5)
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertNotIn('OLD_PENDING_EXPENSE', codes)


class ScoreCapTests(TestCase):
    def test_score_capped_at_100(self):
        expense = _make_expense(
            amount=Decimal('30000'),
            vendor='',
            description='x',
        )
        context = _base_context(
            has_receipt=False,
            duplicate_candidates=[SimpleNamespace(id=99)],
            budget_percentage=110.0,
            pending_days=15,
        )
        result = evaluate_expense(expense, context)
        self.assertLessEqual(result['risk_score'], 100)
        self.assertEqual(result['risk_level'], 'HIGH')


class ReviewSuggestionTests(TestCase):
    def test_receipt_priority(self):
        suggestion = review_suggestion(['MISSING_RECEIPT', 'HIGH_AMOUNT_CRITICAL'])
        self.assertIn('receipt', suggestion.lower())

    def test_budget_priority(self):
        suggestion = review_suggestion(['BUDGET_EXCEEDED'])
        self.assertIn('budget', suggestion.lower())

    def test_default_fallback(self):
        suggestion = review_suggestion(['OLD_PENDING_EXPENSE'])
        self.assertIn('review', suggestion.lower())


class CategoryOutlierRuleTests(TestCase):
    def test_triggers_on_iqr_outlier(self):
        expense = _make_expense(amount=Decimal('20000'))
        context = _base_context(statistical_baseline={
            'median': 3000.0,
            'q1': 2000.0,
            'q3': 5000.0,
            'iqr': 3000.0,
            'upper_fence': 9500.0,
            'mean': 3500.0,
            'std_dev': 1500.0,
            'z_score': 11.0,
            'is_iqr_outlier': True,
            'sample_size': 20,
        })
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertIn('CATEGORY_OUTLIER', codes)

    def test_triggers_on_high_z_score(self):
        expense = _make_expense(amount=Decimal('8000'))
        context = _base_context(statistical_baseline={
            'median': 3000.0,
            'q1': 2000.0,
            'q3': 5000.0,
            'iqr': 3000.0,
            'upper_fence': 9500.0,
            'mean': 3500.0,
            'std_dev': 1500.0,
            'z_score': 3.0,
            'is_iqr_outlier': False,
            'sample_size': 15,
        })
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertIn('CATEGORY_OUTLIER', codes)

    def test_does_not_trigger_when_normal(self):
        expense = _make_expense(amount=Decimal('4000'))
        context = _base_context(statistical_baseline={
            'median': 3000.0,
            'q1': 2000.0,
            'q3': 5000.0,
            'iqr': 3000.0,
            'upper_fence': 9500.0,
            'mean': 3500.0,
            'std_dev': 1500.0,
            'z_score': 0.33,
            'is_iqr_outlier': False,
            'sample_size': 20,
        })
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertNotIn('CATEGORY_OUTLIER', codes)

    def test_does_not_trigger_when_no_baseline(self):
        expense = _make_expense(amount=Decimal('50000'))
        context = _base_context(statistical_baseline=None)
        result = evaluate_expense(expense, context)
        codes = [r['code'] for r in result['triggered_rules']]
        self.assertNotIn('CATEGORY_OUTLIER', codes)


class StatisticalBaselineComputationTests(TestCase):
    def test_computes_correct_stats(self):
        from analytics.rule_context import _category_statistical_baseline
        from unittest.mock import MagicMock

        amounts = [Decimal(x) for x in [1000, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000]]
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.exclude.return_value = mock_qs
        mock_qs.values_list.return_value = mock_qs
        mock_qs.order_by.return_value = amounts

        expense = _make_expense(amount=Decimal('15000'))
        expense.category = 'OFFICE'
        from datetime import date
        expense.date = date(2026, 7, 1)

        result = _category_statistical_baseline(mock_qs, expense)
        self.assertIsNotNone(result)
        self.assertEqual(result['sample_size'], 10)
        self.assertGreater(result['z_score'], 2)
        self.assertTrue(result['is_iqr_outlier'])
        self.assertIn('median', result)
        self.assertIn('upper_fence', result)

    def test_returns_none_when_insufficient_data(self):
        from analytics.rule_context import _category_statistical_baseline, STATISTICAL_MINIMUM_COUNT
        from unittest.mock import MagicMock

        amounts = [Decimal(x) for x in [1000, 2000, 3000]]
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.exclude.return_value = mock_qs
        mock_qs.values_list.return_value = mock_qs
        mock_qs.order_by.return_value = amounts

        expense = _make_expense(amount=Decimal('5000'))
        from datetime import date
        expense.date = date(2026, 7, 1)

        result = _category_statistical_baseline(mock_qs, expense)
        self.assertIsNone(result)


class EvaluateExpenseResponseStructureTests(TestCase):
    def test_response_has_required_keys(self):
        expense = _make_expense()
        context = _base_context()
        result = evaluate_expense(expense, context)
        required_keys = {'risk_score', 'risk_level', 'triggered_rules',
                         'rule_count', 'recommendations', 'review_suggestion'}
        self.assertTrue(required_keys.issubset(result.keys()))

    def test_triggered_rule_has_required_fields(self):
        expense = _make_expense(vendor='')
        context = _base_context()
        result = evaluate_expense(expense, context)
        self.assertTrue(len(result['triggered_rules']) > 0)
        rule = result['triggered_rules'][0]
        required = {'code', 'name', 'category', 'message', 'score',
                    'severity', 'recommendation'}
        self.assertTrue(required.issubset(rule.keys()))
