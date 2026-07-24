# User Roles

Roles are workspace-specific. The same user can have different roles in different organizations.

## Owner

Owners can:

- Create and manage workspace data
- Invite staff members and cancel pending invitations
- View and manage team members and roles
- Review submitted expenses (SUBMITTED / IN_REVIEW status)
- Start review, approve, reject, or return expenses for corrections
- View the approval audit trail for any expense
- Configure and toggle business rules (Rules page)
- Create, pause, update, and remove budgets
- View organization-wide approved expense reports and analytics
- Export reports as CSV and PDF
- View vendor analytics, rule performance metrics, and ML anomaly results
- View activity logs for the workspace

Owner sidebar: Overview, Expenses, Approvals, Budgets, Reports, Insights, Rules, Vendors, Team, Activity, Settings

## Staff

Staff can:

- Save expenses as Draft before submitting
- Submit expenses for approval
- Upload receipts and use AI-assisted receipt scanning
- Correct and resubmit rejected or returned expenses
- View their own expense records and status history
- View their own reports, insights, and vendor data
- View read-only team information

Staff cannot:

- Manage invitations or member roles
- Approve, reject, or return expenses
- Manage budgets
- Access business rule configuration
- View other members' expenses or organization-wide analytics

Staff sidebar: Overview, Expenses, Reports, Insights, Vendors, Team, Activity, Settings

## Superuser / Platform Admin

Superusers use Django Admin/Jazzmin (`/admin/`) to manage platform data. This role is separate from workspace owner/staff behavior in the frontend.

Superusers can inspect or manage:

- Users and authentication
- Organizations and memberships
- Invitations
- Expenses and approval audit logs
- Business rules (enable/disable, adjust scores)
- Budgets and alerts
- Receipts
- Notifications
- Activity logs

## Multi-Workspace Behavior

When the active workspace changes:

- The frontend refetches all workspace-scoped data via TanStack Query.
- API requests include the selected `X-Organization-ID` header.
- Owner/staff actions update according to the user's role in that workspace.
- Data from other organizations is never shown in the current workspace.
