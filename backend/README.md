# Vyapar Margadarshan — Backend

Django REST API for the Vyapar Margadarshan expense management platform.

**Live API:** `https://vyaparmd.tech/api/`

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements/development.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_business_rules
python manage.py createsuperuser
python manage.py runserver
```

## Apps

| App | Purpose |
|-----|---------|
| `users` | Custom user model, registration, login, JWT auth, Google OAuth |
| `organizations` | Workspaces, membership, roles, invitations |
| `expenses` | Expense CRUD, approval workflow (Draft→Submitted→In Review→Approved/Rejected/Returned), audit trail |
| `receipts` | Receipt upload, Gemini Vision OCR processing |
| `budgets` | Category and org-wide budgets with threshold alerts |
| `analytics` | Rule-based expert system, ML anomaly detection, spending analytics, AI insights, PDF/CSV exports |
| `notifications` | In-app notifications for approvals, rejections, budget alerts |
| `activity_logs` | Organization-scoped audit trail with Jazzmin admin dashboard |

## Key Modules

- `analytics/rule_knowledge_base.py` — 15 static business rules
- `analytics/rule_engine.py` — Inference engine (DB rules → static fallback)
- `analytics/rule_context.py` — Context builder: baselines, IQR/z-score, monthly spike
- `analytics/approval_routing.py` — Rule-driven auto-approve / priority-review routing
- `analytics/ml_anomaly.py` — Isolation Forest unsupervised anomaly detection
- `expenses/audit.py` — ApprovalAuditLog helper

## Management Commands

```bash
python manage.py seed_business_rules   # Seed/update 15 business rules in DB
```

## Tests

```bash
python manage.py test          # 217 tests
python manage.py check
```

## Admin

Django Admin with Jazzmin: `http://127.0.0.1:8000/admin/`
Live: `https://vyaparmd.tech/admin/`
