# Workflows

**Live:** [https://vyaparmd.tech](https://vyaparmd.tech)

## Create Workspace

1. Register or log in.
2. Create a new organization/workspace during onboarding or workspace setup.
3. The creator becomes the owner of that workspace.
4. The workspace becomes available in the organization switcher.

## Invite Member

1. Owner opens the Team page.
2. Owner selects Invite by email.
3. Owner enters the email address and role.
4. Backend creates a pending invitation and sends an email via Brevo.
5. The invitation appears in the pending invitations list.

## Accept Invite as New User

1. User opens the invitation link.
2. User registers a new account.
3. Backend validates the invitation token.
4. User becomes a member of the invited workspace.
5. User is redirected into the app.

## Accept Invite as Existing User

1. User opens the invitation link.
2. User logs in with an existing account.
3. Backend validates the invitation token and email rules.
4. Membership is created for the invited workspace.
5. The workspace becomes available in the organization switcher.

## Cancel Invitation

1. Owner opens Team.
2. Owner finds the pending invitation.
3. Owner cancels it.
4. The invitation status changes to cancelled and the link is no longer usable.

## Switch Workspace

1. User opens the organization switcher in the topbar.
2. User selects a workspace.
3. Frontend updates the active organization.
4. Pages refetch data using `X-Organization-ID`.
5. Role-specific actions update for the selected workspace.

## Submit Expense (Staff)

1. Staff opens Expenses and selects Add expense.
2. Staff enters amount, category, vendor, date, title, and description.
3. Staff optionally uploads or scans a receipt.
4. Staff can **save as draft** or **submit directly**.
5. On submission, the rule engine evaluates the expense automatically.
6. Low-risk expenses (score ≤ 10) are auto-approved by the routing engine.
7. Others enter the owner's approval queue as SUBMITTED.

## Submit Draft Expense

1. Staff saves an expense as Draft.
2. Staff edits and finalizes the draft.
3. Staff clicks Submit on the draft.
4. Expense moves to SUBMITTED status and enters the approval queue.

## Approve Expense

1. Owner opens Approvals.
2. Owner sees expenses with status SUBMITTED or IN_REVIEW.
3. Owner optionally clicks Start Review to mark it IN_REVIEW.
4. Owner reviews amount, category, vendor, date, notes, receipt, and rule signals.
5. Owner approves.
6. Approved expense is included in budgets, reports, dashboard metrics, and CSV exports.

## Reject Expense

1. Owner opens Approvals.
2. Owner selects an expense.
3. Owner enters a rejection reason and confirms.
4. Expense status changes to REJECTED.
5. Submitter is notified and can correct and resubmit.

## Return Expense for Changes

1. Owner opens Approvals.
2. Owner selects an expense that needs corrections without full rejection.
3. Owner enters a return reason.
4. Expense status changes to RETURNED.
5. Submitter edits the expense and resubmits.

## Correct and Resubmit

1. Submitter opens a REJECTED or RETURNED expense.
2. Submitter edits the required fields.
3. Submitter saves — expense moves back to SUBMITTED.
4. Expense re-enters the approval queue.

## View Approval Audit Trail

1. Open any expense.
2. The audit trail shows every status transition: who made it, when, the reason, and the rule engine snapshot at that point.

## Budget Tracking

1. Owner opens Budgets.
2. Owner creates a budget for all categories or a specific category.
3. Approved expenses are compared against budget limits.
4. Budget Exceeded and Budget Pressure rules flag risky submissions automatically.

## Report Export

1. User opens Reports.
2. User selects date range and optional filters.
3. Report loads approved expense data for the active workspace and permitted role.
4. User selects Export CSV or Export PDF.

## Configure Business Rules

1. Owner opens Rules page (owner-only).
2. Owner can enable/disable any rule and adjust its score.
3. Changes take effect immediately for the next expense evaluation.
4. Rules can also be managed in Django Admin.
