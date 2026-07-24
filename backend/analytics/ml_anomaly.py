"""
ML-based anomaly detection using Isolation Forest.

Complements the rule-based engine with unsupervised learning:
trains on historical approved expenses to detect statistical outliers
that hand-crafted rules might miss. Falls back gracefully when
insufficient data exists for meaningful model training.
"""
import logging
from datetime import timedelta
from decimal import Decimal

import numpy as np
from django.utils import timezone

_logger = logging.getLogger(__name__)

MINIMUM_TRAINING_SAMPLES = 30
CONTAMINATION = 0.05


def _extract_features(expenses):
    """Extract numerical feature vectors from expense queryset.

    Features: amount, day_of_week, day_of_month, category_encoded.
    """
    categories = sorted({e.category for e in expenses})
    cat_index = {c: i for i, c in enumerate(categories)}

    features = []
    for e in expenses:
        features.append([
            float(e.amount),
            e.date.weekday(),
            e.date.day,
            cat_index.get(e.category, 0),
        ])
    return np.array(features), cat_index


def detect_ml_anomalies(organization, *, lookback_days=180, top_n=10):
    """Run Isolation Forest on the organization's recent expenses.

    Returns a list of expense IDs flagged as anomalies with their
    anomaly scores, or None if insufficient data.
    """
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        _logger.warning('scikit-learn not installed; ML anomaly detection unavailable.')
        return None

    from expenses.models import Expense

    cutoff = timezone.localdate() - timedelta(days=lookback_days)
    expenses = list(
        Expense.objects.filter(
            organization=organization,
            status='APPROVED',
            date__gte=cutoff,
        ).select_related('user').order_by('date')
    )

    if len(expenses) < MINIMUM_TRAINING_SAMPLES:
        return None

    features, cat_index = _extract_features(expenses)

    model = IsolationForest(
        n_estimators=100,
        contamination=CONTAMINATION,
        random_state=42,
    )
    model.fit(features)

    scores = model.decision_function(features)
    predictions = model.predict(features)

    anomalies = []
    for i, (expense, score, pred) in enumerate(zip(expenses, scores, predictions)):
        if pred == -1:
            anomalies.append({
                'expense_id': expense.id,
                'title': expense.title,
                'amount': float(expense.amount),
                'category': expense.category,
                'vendor': expense.vendor or '',
                'date': expense.date.isoformat(),
                'anomaly_score': round(float(-score), 4),
                'user': expense.user.get_full_name() or expense.user.username,
            })

    anomalies.sort(key=lambda x: x['anomaly_score'], reverse=True)
    return anomalies[:top_n]
