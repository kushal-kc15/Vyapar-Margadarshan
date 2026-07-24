# Features

**Live:** [https://vyaparmd.tech](https://vyaparmd.tech)

## Multi-Workspace Support

Users can belong to multiple organizations. The active workspace is sent through the `X-Organization-ID` request header so backend data stays scoped to the selected organization.

## Owner and Staff Roles

Roles are assigned per workspace. A user can be an owner in one organization and staff in another.

## Expense Submission

Users can record expenses with:

- Title and description
- Amount and date
- Category
- Vendor
- Receipt attachment

Staff can save as **Draft** before submitting, or submit directly. Submitted expenses go through the approval workflow.

## Multi-Stage Approval Workflow

Expenses move through a structured workflow:

```
DRAFT → SUBMITTED → IN_REVIEW → APPROVED
                              ↘ REJECTED
                              ↘ RETURNED → (edit) → SUBMITTED
```

- **Draft**: saved but not yet submitted
- **Submitted**: sent for review; rule engine evaluates it immediately
- **In Review**: owner is actively reviewing
- **Approved / Rejected**: final decisions
- **Returned**: sent back for corrections without full rejection

## Rule-Based Expert System

Every submitted expense is evaluated by a configurable knowledge base of 15 business rules across 7 categories:

| Category | Rules |
|----------|-------|
| Spending Pattern | High Category Amount, High Vendor Amount, Monthly Spike, Statistical Outlier |
| Financial Risk | High Amount (Critical / Elevated / Routine) |
| Duplicate Detection | Duplicate Candidate |
| Compliance | Missing Receipt, Weak Description, Missing Vendor |
| Vendor Risk | New Vendor |
| Budget | Budget Exceeded, Budget Pressure |
| Approval | Old Pending Expense |

Each rule contributes a risk score. The total score determines LOW / MEDIUM / HIGH risk level. Owners can enable/disable rules and adjust scores from the Rules page or Django Admin.

## Rule-Driven Approval Routing

When an expense is submitted, the routing engine automatically:

- **Auto-approves** low-risk expenses (score ≤ 10, no significant flags)
- Sends medium-risk expenses for **standard review**
- Flags high-risk expenses (score ≥ 50) for **priority review**

## Approval Audit Trail

Every status transition is recorded in an `ApprovalAuditLog` with:

- Who made the transition and when
- Previous and new status
- Reason (for rejections and returns)
- Rule engine snapshot at the time of decision

Available at `GET /api/expenses/{id}/audit-trail/`.

## ML Anomaly Detection

Isolation Forest model trained on historical approved expenses detects statistical outliers that rule-based checks might miss. Available at `GET /api/analytics/ml-anomalies/` (requires ≥ 30 approved expenses for training).

## Receipt Upload and AI Scanning

Receipt files can be uploaded and scanned with Gemini Vision through the Django backend. API keys stay server-side, and extracted fields are shown to the user for review before an expense is created.

## Budgets and Alerts

Owners can create category or all-category budgets by period. Budget thresholds highlight spending that is near or over the configured limit.

## Analytics

- Spending trends (daily / weekly / monthly)
- Category breakdowns and vendor summaries
- Period comparisons
- Budget burn rate
- Unusual expense signals (rule-based anomaly cards)
- Rule performance metrics (trigger frequency, approval/rejection rates, auto-approval rate)
- AI-generated spending summaries via Gemini

## Reports and Exports

Reports use approved expenses only. Support date filtering, category/vendor filtering, approved expense tables, CSV export, and PDF report generation.

## Team Invitations

Owners can invite users to a workspace by email. Invitations support new-user and existing-user acceptance flows, and can be cancelled before acceptance.

## Transactional Email

Email notifications for approvals, rejections, and invitations are sent via Brevo (Sendinblue) using django-anymail.

## Staff Navigation

Staff users see: Overview, Expenses, Reports, Insights, Vendors, Team, Activity, Settings. Owner-only sections (Approvals, Budgets, Rules) are hidden.

## Admin Dashboard

Django Admin is styled with Jazzmin and configured as a website manager console for platform-level management, including business rule editing.

## Theme Switching

The frontend supports light, dark, and system theme preferences.

## Notifications and Activity Logs

Notifications and activity logs for expense changes, approvals, rejections, returns, budget alerts, and team events.
