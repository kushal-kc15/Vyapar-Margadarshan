from django.urls import path
from . import views

urlpatterns = [
    path('overview/', views.overview, name='analytics-overview'),
    path('report-detail/', views.report_detail, name='analytics-report-detail'),
    path('export-csv/', views.export_csv, name='analytics-export-csv'),
    path('export-pdf/', views.export_pdf, name='analytics-export-pdf'),
    path('spending-trends/', views.spending_trends, name='spending-trends'),
    path('category-breakdown/', views.category_breakdown, name='category-breakdown'),
    path('period-comparison/', views.period_comparison, name='period-comparison'),
    path('vendor-summary/', views.vendor_summary, name='vendor-summary'),
    path('budget-burn-rate/', views.budget_burn_rate, name='budget-burn-rate'),
    path('ai-insights/', views.ai_insights, name='analytics-ai-insights'),
    path('rule-based-advice/', views.rule_based_advice, name='analytics-rule-based-advice'),
    path('anomalies/', views.anomalies, name='analytics-anomalies'),
    path('rules/', views.rules, name='analytics-rules'),
    path('rules/<str:code>/', views.rule_update, name='analytics-rule-update'),
    path('routing/<int:expense_id>/', views.routing_preview, name='analytics-routing-preview'),
]
