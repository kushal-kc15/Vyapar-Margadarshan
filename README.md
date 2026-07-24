# Vyapar Margadarshan

Business Expense Management Platform

**Live:** [https://vyaparmd.tech](https://vyaparmd.tech)

Vyapar Margadarshan is a full-stack expense management system for small teams and organizations. It helps owners and staff record expenses, upload receipts, manage approvals, track budgets, and generate approved-spend reports — all from a single workspace-aware dashboard with a built-in rule-based expert system for anomaly detection.

## Problem Statement

Many small businesses track spending through spreadsheets, chat messages, paper receipts, and manual approvals. This creates delays, missing receipts, unclear budget usage, and weak visibility into approved spending. Vyapar Margadarshan provides a structured workflow for recording, reviewing, and reporting business expenses while keeping each organization's data separate.

## Key Features

**Expense Management**
- Submit expenses with category, vendor, amount, date, and description
- Receipt upload with Gemini Vision AI-assisted data extraction
- Multi-stage approval workflow: Draft → Submitted → In Review → Approved/Rejected/Returned
- Correct and resubmit rejected or returned expenses

**Approval Intelligence**
- Rule-based expert system with 15 configurable business rules
- Automatic approval routing — low-risk expenses auto-approved, high-risk flagged for review
- Approval audit trail recording every status transition with rule snapshots
- ML anomaly detection using Isolation Forest on historical spend patterns

**Analytics and Reporting**
- Budget tracking with threshold alerts
- Approved-only analytics, category breakdowns, vendor summaries, spending trends
- Rule performance metrics (trigger frequency, approval/rejection rates)
- AI-generated spending summaries via Gemini
- CSV and PDF report exports

**Workspace and Team**
- Multi-workspace organization support with role switching
- Owner and staff roles
- Team invitations with cancellation support
- Activity logs and notifications
- Transactional email via Brevo (Sendinblue)

**Platform**
- Jazzmin-powered admin dashboard
- DB-managed business rules with admin toggle/edit
- Light/dark theme support
- TanStack Query for efficient data fetching and caching

## Live URL

**[https://vyaparmd.tech](https://vyaparmd.tech)**

- API: `https://vyaparmd.tech/api/`
- Admin: `https://vyaparmd.tech/admin/`

## Tech Stack

**Frontend**
- React 18
- Vite
- Tailwind CSS
- Axios
- React Router v6
- TanStack Query v5
- Lucide icons

**Backend**
- Django 4.2
- Django REST Framework
- Simple JWT
- Django Jazzmin
- django-filter
- django-anymail (Brevo)
- scikit-learn (Isolation Forest ML)
- Celery and Redis (background tasks)

**Database**
- SQLite for local development
- PostgreSQL in production via `DATABASE_URL`

**AI / ML**
- Gemini Vision for receipt scanning
- Gemini for AI spending summaries
- Isolation Forest for unsupervised anomaly detection

## Quick Start

Run the backend and frontend in separate terminals.

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements/development.txt
cp .env.example .env            # Windows: Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_business_rules
python manage.py createsuperuser
python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local      # Windows: Copy-Item .env.example .env.local
npm run dev
```

Default local URLs:

| Service | URL |
|---------|-----|
| Frontend | `http://localhost:5173` |
| Backend API | `http://127.0.0.1:8000/api/` |
| Admin dashboard | `http://127.0.0.1:8000/admin/` |

## Environment Variables

Use `.env.example` files as templates only. Never commit real secrets, API keys, database passwords, or JWT signing keys.

See [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) for a full variable reference.

## User Roles

| Role | Capabilities |
|------|-------------|
| **Owner** | Manage workspace, invite team, approve/reject/return expenses, manage budgets, view org-wide reports and analytics, configure business rules |
| **Staff** | Submit expenses (draft or direct), correct returned/rejected expenses, view own expense history, reports, insights, and vendors |
| **Superuser** | Full platform access via Django Admin/Jazzmin |

## Approval Workflow

```
DRAFT → SUBMITTED → IN_REVIEW → APPROVED
                              ↘ REJECTED
                              ↘ RETURNED → (edit) → SUBMITTED
```

- **DRAFT**: saved but not yet submitted
- **SUBMITTED**: sent for owner review; triggers rule engine evaluation
- **IN_REVIEW**: owner has started actively reviewing
- **APPROVED / REJECTED**: final decisions
- **RETURNED**: sent back for corrections without rejection

Low-risk expenses (rule score ≤ 10) are auto-approved by the routing engine.

## Rule-Based Expert System

15 business rules across 7 categories evaluate every submitted expense:

| Category | Rules |
|----------|-------|
| Spending Pattern | High Category Amount, High Vendor Amount, Monthly Spike, Statistical Outlier |
| Financial Risk | High Amount (Critical/Elevated/Routine) |
| Duplicate Detection | Duplicate Candidate |
| Compliance | Missing Receipt, Weak Description, Missing Vendor |
| Vendor Risk | New Vendor |
| Budget | Budget Exceeded, Budget Pressure |
| Approval | Old Pending Expense |

Owners can enable/disable rules and adjust scores via `/rules` in the UI or Django Admin.

## Testing

```bash
cd backend
python manage.py test          # 217 tests
python manage.py check
```

```bash
cd frontend
npm run build
```

## Documentation

- [Project Overview](docs/PROJECT_OVERVIEW.md)
- [Features](docs/FEATURES.md)
- [User Roles](docs/USER_ROLES.md)
- [Workflows](docs/WORKFLOWS.md)
- [Installation](docs/INSTALLATION.md)
- [Environment](docs/ENVIRONMENT.md)
- [Testing](docs/TESTING.md)
- [Screenshots](docs/SCREENSHOTS.md)

## Project Status

Completed as a final-year academic project at SOCH College of IT. Live at [vyaparmd.tech](https://vyaparmd.tech).

Core features implemented: expense management, multi-stage approval workflow, rule-based expert system, ML anomaly detection, organization scoping, role-based access, budget tracking, AI receipt scanning, analytics, team invitations, transactional email, and admin dashboard.
