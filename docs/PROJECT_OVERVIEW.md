# Project Overview

**Live:** [https://vyaparmd.tech](https://vyaparmd.tech)

Vyapar Margadarshan is a business expense management platform built for small organizations. The system gives each workspace a controlled place to record spending, collect receipts, route approvals intelligently, track budgets, detect unusual expenses, and report on approved business costs.

## What It Does

The platform supports a complete expense lifecycle with intelligent approval routing:

1. A workspace owner creates an organization.
2. Staff members are invited to the workspace.
3. Staff submit expenses with amount, category, vendor, date, notes, and optional receipt.
4. The rule-based expert system (15 rules) evaluates each submission automatically.
5. Low-risk expenses are auto-approved; others enter the owner's review queue.
6. Owners can approve, reject, or return expenses for corrections.
7. Every status transition is recorded in an approval audit trail.
8. Approved expenses feed budgets, reports, vendor analytics, dashboards, and exports.

## What Makes It Different

Most small-business expense tools are passive — they record expenses but do not help reviewers prioritize. Vyapar Margadarshan adds:

- **Rule-based expert system**: 15 configurable rules flag unusual expenses before an owner opens them
- **Automatic routing**: low-risk expenses auto-approve; high-risk ones surface for priority review
- **ML anomaly detection**: Isolation Forest catches statistical outliers rules might miss
- **Audit trail**: every approval decision is recorded with a rule engine snapshot for explainability
- **Multi-stage workflow**: Draft → Submitted → In Review → Approved/Rejected/Returned

## Target Users

- Small business owners who need visibility and control over team spending.
- Staff members who need a simple structured way to submit and track expenses.
- Finance reviewers who need approved-only reports and anomaly signals.
- Platform administrators managing the system through Django Admin/Jazzmin.

## Tech Summary

| Layer | Stack |
|-------|-------|
| Frontend | React 18, Vite, Tailwind CSS, TanStack Query |
| Backend | Django 4.2, Django REST Framework, Simple JWT |
| Database | PostgreSQL (production), SQLite (local) |
| AI/ML | Gemini Vision (receipts), Gemini (summaries), scikit-learn Isolation Forest |
| Email | Brevo via django-anymail |
| Hosting | vyaparmd.tech |

## Project Status

Completed as a final-year academic project at SOCH College of IT. 217 backend tests. Deployed live at [vyaparmd.tech](https://vyaparmd.tech).
