# Vyapar Margadarshan — Final Defense Guide

This guide is based on the current backend and frontend source code. It deliberately excludes deployment and hosting.

## 1. Project overview

Vyapar Margadarshan is a multi-workspace business expense management platform for small businesses and teams. It replaces scattered receipts, spreadsheets, and informal approval messages with one organized system.

The main users are:

- **Owners**, who create and manage workspaces, invite members, review expenses, define budgets, and view business-wide reports.
- **Staff**, who submit and track their own expenses, upload receipts, correct rejected expenses, and view workspace information without changing owner-controlled settings.
- **Platform administrators**, who maintain system data through the Django/Jazzmin admin dashboard.

The problem is that small teams often record spending in different places. This makes it difficult to know what was spent, who spent it, whether it was authorized, and whether the business is exceeding its budget. Vyapar Margadarshan gives each expense a clear owner, status, workspace, and audit trail.

The main objective is to provide a simple, controlled, and intelligent expense workflow: capture expenses, verify staff submissions, monitor budgets, analyze approved spending, and keep each workspace's data separate.

## 2. System architecture

The system uses a client-server architecture:

```text
React + Vite + Tailwind frontend
            |
     Axios HTTP requests
  Bearer JWT + X-Organization-Id
            |
Django REST Framework backend
     |          |          |
  SQLite     Gemini API   Email
 local data   AI features  verification/invites
```

### Frontend

The React application in `frontend/src` renders the interface, handles navigation, stores the current login/workspace state, validates forms, and calls backend APIs. Vite runs and builds the app. Tailwind and shared UI components provide styling.

### Backend

The Django project in `backend` contains REST APIs and business rules. Django REST Framework converts requests and model data to JSON. The backend is the final authority for permissions; hiding a button in React is only a user-interface convenience.

### Database

The local database is SQLite. Django's ORM manages tables and relationships through models and migrations. Most business records contain an `organization` foreign key, which is the basis for workspace separation.

### AI integration

Gemini is called only by the backend. It is used for receipt field extraction and expense insight generation. The API key therefore does not need to be exposed to the browser.

### Frontend-to-backend communication

`frontend/src/lib/api.js` creates one Axios client with `/api` as the default base path. A request interceptor adds:

- `Authorization: Bearer <access token>` for authentication.
- `X-Organization-Id: <active organization id>` for workspace context.

A response interceptor clears the local session on a `401 Unauthorized` response. Pages use `api.get`, `api.post`, `api.patch`, and `api.delete`, then update React state from the returned JSON.

### Authentication at a high level

The user can register with email/password or sign in through Google. Email/password registration requires email verification. After successful login, the backend issues Simple JWT refresh and access tokens. The frontend currently stores and uses the access token in its local authentication state.

The backend also implements login throttling, password strength checks, failed-attempt account locking, password reset, hashed verification/reset tokens, optional two-factor authentication, and JWT blacklist support. Login-time 2FA enforcement is controlled by `TWO_FACTOR_LOGIN_ENABLED` and is disabled by default while preserving user preferences.

### Workspace context

Workspace resolution is implemented in `backend/organizations/context.py`. It uses this priority:

1. `X-Organization-Id` request header, if it belongs to the user.
2. The user's saved `active_organization`.
3. The user's first membership.

Switching a workspace updates `User.active_organization`. Every scoped backend query then filters by the resolved membership and organization.

### Owner/staff roles

`Membership` links a user to an organization and stores either `OWNER` or `STAFF`. The same user can have different roles in different workspaces. Owner-only frontend routes are protected, and the backend separately checks owner membership before allowing sensitive actions.

## 3. Backend structure

The backend entry points are `backend/manage.py`, `backend/vyapar_margadarshan/settings`, and `backend/vyapar_margadarshan/urls.py`.

### Main Django apps

| App | Responsibility |
|---|---|
| `users` | Custom user, registration, login, JWT, Google login, verification, password reset, 2FA, profile and preferences |
| `organizations` | Workspaces, memberships, roles, invitations, switching, and tenant context |
| `expenses` | Expense CRUD, status workflow, approvals, dashboard metrics, vendor analysis, CSV export |
| `receipts` | Receipt images, Gemini extraction, verification, and expense creation |
| `budgets` | Spending limits, periods, usage calculation, threshold alerts |
| `analytics` | Approved-spend reports, trends, comparisons, CSV, AI insights, and anomaly detection |
| `activity_logs` | Workspace audit events |
| `notifications` | User-specific in-app notifications |

### Important serializers

- `UserSerializer` and `RegisterSerializer` expose safe user fields and validate registration.
- `OrganizationSerializer`, `OrganizationMemberSerializer`, and `InvitationSerializer` shape workspace/team responses.
- `ExpenseSerializer` makes status, reviewer fields, user, and receipt metadata read-only. This prevents a client from declaring its own approval.
- `ReceiptUploadSerializer`, `ReceiptVerifySerializer`, and `ReceiptSerializer` validate uploads/corrections and return scan information.
- `BudgetSerializer` derives dates, prevents overlapping active budgets for the same category, and calculates spent, remaining, and percentage used.
- `ActivityLogSerializer` and `NotificationSerializer` support read-only feeds.

### Main API groups

- `/api/auth/`: register, login, Google login, token refresh, verification, password reset, profile, password, preferences, avatar, and user data export.
- `/api/organizations/`: workspace CRUD, memberships, switch, leave, members, invite, role update, member removal, and statistics.
- `/api/invitations/`: list, status, accept, resend, cancel, and pending invitations.
- `/api/expenses/`: CRUD, dashboard metrics, personal expenses, pending approvals, approve, reject, vendor analytics, and CSV export.
- `/api/receipts/`: upload/list/detail, verify scan data, and create an expense.
- `/api/budgets/` and `/api/budget-alerts/`: budget CRUD, summary, category breakdown, alert checks, and mark-read.
- `/api/analytics/`: overview, detailed reports, trends, category/vendor analysis, comparison, burn rate, CSV, AI insights, and anomalies.
- `/api/activity-logs/` and `/api/notifications/`: scoped read-only feeds and notification actions.

### Expense workflow rules

- A staff-created expense starts as `PENDING`.
- An owner-created expense is automatically `APPROVED`.
- Only the original submitter can edit an expense.
- Only `PENDING` or `REJECTED` expenses can be edited.
- When the submitter edits a rejected expense, it automatically becomes `PENDING`; old reviewer details and rejection reason are cleared.
- Only an owner in the active organization can approve or reject another user's pending expense.
- The owner cannot use the decision action on their own expense.
- A rejection requires/records a reason; decisions record `reviewed_by` and `reviewed_at`.
- Approval triggers budget checks. Decisions create activity logs and notifications; approval/rejection email helpers also exist.

These rules are mainly in `backend/expenses/views.py`, with data protection in `backend/expenses/serializers.py`.

### Budget logic

A budget belongs to one organization and can cover one category or `ALL`. Its period can be daily, weekly, monthly, or yearly. The model derives an inclusive start/end range when dates are omitted.

Budget usage queries only `APPROVED` expenses within the same organization and date range. A category budget includes only matching expenses; `ALL` includes all approved categories. Active budgets for the same category cannot overlap in date range.

Threshold usage creates a `BudgetAlert` and sends in-app/email warnings to owners. The API exposes total budget, spent amount, remaining amount, and percentage used.

### Reports and analytics

Analytics starts from approved expenses in the active organization. Owners receive organization-wide results; staff-level analytics functions restrict results to the staff user's own approved expenses. The Reports page itself is owner-only in the current React routes.

The backend calculates totals, counts, averages, category distribution, vendor totals, daily/weekly/monthly trends, current-versus-previous comparison, budget burn rate, and anomaly candidates. CSV generation includes formula-injection protection for text values.

There is no separate stored `Report` table. Reports are generated dynamically from `Expense` and `Budget` data when requested.

### Team invitations

An owner creates an `Invitation` containing email, role, UUID token, expiry, inviter, and status. The invitation is emailed, or an existing standalone user can receive an in-app path. The recipient must use the same email address.

Acceptance creates a membership, marks the invitation accepted/used, and switches the user into the joined organization. Invitations can be resent, cancelled, or marked expired. The code prevents duplicate membership and protects the last owner from removal/demotion.

### Admin/Jazzmin

`jazzmin` is installed before Django admin in `INSTALLED_APPS`. `JAZZMIN_SETTINGS` and `JAZZMIN_UI_TWEAKS` customize branding, navigation, icons, colors, and model order. Admin classes register users, organizations, memberships, invitations, expenses, budgets, alerts, receipts, notifications, and activity logs. A custom admin index template provides platform-level management information.

### Settings and environment

`backend/vyapar_margadarshan/settings/base.py` contains shared settings; `development.py` contains local overrides. Environment values are read with `python-decouple`.

Important variables include `SECRET_KEY`, `DATABASE_URL`, `CORS_ALLOWED_ORIGINS`, JWT lifetimes/signing key, email settings, frontend URL, Google client ID, `GEMINI_API_KEY`, Gemini model names, receipt size/types, and optional Celery/Redis OCR queue settings. Secrets must remain in `.env`, never source code.

## 4. Frontend structure

### Important folders/files

- `frontend/src/main.jsx`: mounts providers for theme, Google OAuth, router, authentication, and toast messages.
- `frontend/src/App.jsx`: defines public, setup, protected, and owner-only routes.
- `frontend/src/context/AuthContext.jsx`: login state, session hydration, membership normalization, workspace switching, and auth actions.
- `frontend/src/context/ThemeContext.jsx`: light/dark/system preference and system-theme observation.
- `frontend/src/lib/api.js`: Axios base client and token/workspace interceptors.
- `frontend/src/lib`: categories, currency, dates, OAuth hints, invite flow, and utility helpers.
- `frontend/src/components`: reusable layout, form, feedback, table, modal, receipt, navigation, chart, money, status, and notification components.
- `frontend/src/design-system`: newer shared primitives for cards, buttons, headers, modals, tables, status, and feedback.

### Routing and layout

Public routes include the landing, login, registration, verification, password recovery, and invitation pages. Authenticated users without a workspace use workspace-choice/setup routes. Authenticated workspace users enter `AppShell`, which combines `Sidebar`, `Topbar`, and the selected page through React Router's `Outlet`.

Owner-only routes are Approvals, Budgets, Reports, and Vendors. Dashboard, Expenses, Team, Activity, and Settings are accessible to authenticated members, with individual controls adjusted by role.

### Main pages

- **Landing:** explains receipt capture, approvals, budgets, roles, exports, and core benefits; includes calls to login/register.
- **Login/Register:** password and Google entry points, verification handling, invitations, optional OTP flow, validation, and error feedback.
- **WorkspaceChoice/OrgSetup:** select an existing membership, follow a pending invite, or create a workspace.
- **Dashboard:** loads approved spending metrics, recent expenses, pending review items, budgets, and category breakdown. Staff do not see owner budget/review sections.
- **Expenses:** searchable/filterable expense list, pagination, creation/editing, receipt display, AI scanning, and CSV export.
- **Approvals:** owner review tabs and decision modal; shows submitter, details, receipt, and rejection note.
- **Budgets:** owner budget creation/edit/pause/delete plus summary and usage visualization. React also contains read-only rendering, although the route is currently owner-only.
- **Reports:** date preset/custom filters, category/vendor filters, totals, charts, comparison, approved expense rows, CSV export, and on-demand AI insights.
- **Vendors:** owner vendor-spending summary from approved data.
- **Team:** all members can view people; owners can invite, change roles, remove members, and cancel invitations.
- **Activity:** searchable/filterable workspace activity feed.
- **Settings:** profile, password, workspace information, preferences/theme/currency, and leaving a workspace. Workspace fields are disabled for staff.

### Loading, errors, and state

Pages mainly use local React state with `useState`, `useEffect`, `useMemo`, and `useCallback`. Loading skeletons/spinners prevent blank screens. API errors become inline field errors, page retry states, or toast messages. Empty states explain what to do next. Requests use cancellation flags/request IDs where stale responses could overwrite newer state.

## 5. Major features in simple language

### Registration and login

The user creates an account, receives an email verification link, verifies the address, and signs in. Google sign-in can create or reuse an account. The server returns JWTs after successful authentication.

### Multiple workspaces

One user can belong to several businesses. Every membership has its own role. The workspace switcher changes the active organization without requiring a second account.

### Owner and staff roles

Owners control the business workspace. Staff submit and monitor their own expenses. Role checks exist both in React and Django, so direct API calls cannot bypass the intended restriction.

### Expense and receipt capture

Users can type an expense manually or upload a receipt. The receipt is stored separately and can be linked one-to-one with the created expense.

### AI receipt scanning

The image is validated, rotated according to EXIF data, resized, converted to JPEG, and sent to Gemini. Gemini returns vendor, final amount, date, category, notes, confidence, and useful raw text. The user reviews/corrects these fields before creating the expense.

### Approval, rejection, and resubmission

Staff submissions wait for an owner. An owner approves or rejects with context. A rejected expense remains visible to the submitter, who edits it; saving automatically resubmits it for a new decision.

### Budgets

Owners set category or overall limits for a time period. The system compares only approved expenses against the budget and warns when the configured percentage or total limit is reached.

### Reports and CSV

Owners filter approved expenses by dates, category, and vendor. The page explains totals and trends visually. CSV export provides portable report data.

### AI Expense Insights

The backend summarizes approved expense data first, then asks Gemini to explain observations, warnings, and recommended actions. Gemini receives a controlled summary rather than unrestricted database access.

### Staff read-only restrictions

Staff can see team and workspace information but cannot invite/remove members or edit workspace settings. They cannot access owner-only pages through normal routing, and backend permissions protect the corresponding actions.

### Theme switching

The user can choose light, dark, or system theme. The preference is applied to the root document and saved locally; settings can also save the user's theme preference on the backend.

## 6. Main workflows

### Owner creates a workspace

1. The authenticated user opens workspace setup.
2. React posts the organization data to `/api/organizations/`.
3. Django creates `Organization` and an `OWNER` membership in one workflow.
4. The organization becomes the user's active workspace.
5. Protected workspace pages become available.

### Owner invites staff and staff joins

1. Owner opens Team and submits the email and `STAFF` role.
2. Backend verifies owner membership and avoids duplicate active membership/invitation problems.
3. It creates an expiring invitation token and sends the invitation.
4. The recipient opens the link and signs in or registers with the invited email.
5. Accepting creates `Membership`, marks the invitation used/accepted, and activates that workspace.

### Staff submits an expense manually

1. Staff opens Expenses and fills title, amount, date, category, vendor, and description.
2. React posts to `/api/expenses/` with the JWT and workspace header.
3. Backend associates the authenticated user and active organization.
4. Because the role is staff, status becomes `PENDING`.
5. Owners receive an in-app notification, and an activity entry is recorded.

### Staff scans a receipt

1. Staff opens the AI receipt modal and selects a JPEG, PNG, or WebP image.
2. The frontend uploads multipart data to `/api/receipts/`.
3. Backend validates type/size and stores the receipt under the active organization.
4. Gemini extraction runs synchronously by default, or optionally through Celery.
5. Extracted values return to the modal for human review.
6. Staff verifies/corrects the fields.
7. The receipt endpoint creates a linked expense with staff approval rules.

### Owner approves or rejects

1. Owner opens Approvals and loads pending expenses from their active workspace.
2. Owner checks the submitter, amount, description, and receipt.
3. Approve changes status to `APPROVED`; reject changes it to `REJECTED` and records the reason.
4. Reviewer identity/time are stored, and notifications/activity are created.
5. Approval triggers budget checks.

### Staff resubmits a rejected expense

1. Staff sees the rejection reason on their expense.
2. Staff edits the incorrect fields and saves.
3. Backend verifies that they are the original submitter and the current state is rejected.
4. Status returns to `PENDING`; old decision metadata is cleared.
5. Owners are notified for a fresh review.

### Approved expenses affect budgets and reports

1. Once approved, an expense becomes part of official spending queries.
2. Budget serializers sum it when organization, date range, and category match.
3. Analytics includes it in totals, charts, vendors, comparisons, and exports.
4. Pending/rejected expenses remain outside official reports and budget consumption.

### Owner views reports and AI insights

1. Owner selects a date range and optional category/vendor filters.
2. Backend returns a deterministic approved-expense report.
3. Owner can export the same filtered information as CSV.
4. For AI insights, backend prepares an approved-data snapshot.
5. Gemini returns a business-friendly explanation; if Gemini fails, deterministic fallback insights are returned.

## 7. Database relationships

```text
User 1 --- * Membership * --- 1 Organization
User 1 --- * Expense * ------- 1 Organization
User 1 --- * Receipt * ------- 1 Organization
Expense 1 --- 0..1 Receipt
Organization 1 --- * Budget --- 1 User(created_by)
Budget 1 --- * BudgetAlert
Organization 1 --- * Invitation --- 1 User(invited_by)
Organization 1 --- * ActivityLog --- 1 User
User 1 --- * Notification * --- 0..1 Organization
```

`User` also has password-reset and OTP records and an optional `active_organization`. `Expense.reviewed_by` points back to the reviewing user. Deleting an organization cascades its operational records, while deleting the reviewer uses `SET_NULL` so expense history remains.

Data separation is enforced by membership-aware querysets, not merely by IDs sent from the browser. The backend accepts a requested workspace only when the authenticated user has a membership in it.

Approved-only reporting is important because pending means “not yet accepted by the business,” while rejected means “not accepted.” Counting either as official spending would make budgets and financial summaries misleading.

## 8. AI integration

### Receipt scanning

`backend/receipts/services/ai_receipt_extractor.py` uses `google-genai` and the configured `GEMINI_RECEIPT_MODEL`, defaulting to `gemini-2.5-flash`. Temperature is zero and JSON output is requested. The code normalizes amount/date/category/confidence and refuses unusable output.

The extracted fields are vendor, final paid amount, transaction date, app category, short notes, confidence, and visible raw text. Current task application stores common confidence values on the receipt; line items are modeled but the current Gemini prompt does not request them.

### AI insights

`backend/analytics/ai_insights.py` sends Gemini an aggregated snapshot: approved totals/counts, top categories/vendors, comparison data, and recent approved expense summaries for a chosen period. The response is restricted to a summary, 2–4 observations, up to three warnings, and up to three recommendations.

### Why Flash

The configured Flash model is appropriate because receipt extraction and short financial summaries favor low latency and lower cost over long-form reasoning. The exact model is environment-configurable, so the code is not permanently tied to one version.

### Failure behavior and limitations

- A missing API key gives a clear configuration error and lets the user enter the expense manually.
- Invalid file types, oversized files, and non-images are rejected safely.
- Provider or malformed-output failures mark the receipt `FAILED` with a public error rather than exposing internal details.
- Queue failure can fall back to synchronous processing when configured.
- AI insights fall back to backend-generated observations if Gemini fails.
- AI can misread blurred, cropped, handwritten, multilingual, or unusual receipts.
- Confidence is advisory, not proof. Human verification is intentionally required.
- AI insights are guidance, not accounting or financial advice.

## 9. Security and access control

- **Authentication:** DRF uses `JWTAuthentication`; protected APIs default to `IsAuthenticated`.
- **Token controls:** access/refresh lifetimes are configurable; refresh rotation and blacklisting are enabled by default. Auth endpoints are throttled.
- **Account protection:** five failed password attempts lock the account temporarily. Password validators and strength scoring are used.
- **Sensitive token storage:** verification, reset, and OTP values are stored as hashes where implemented, reducing damage if database contents are exposed.
- **Role control:** owner actions check the membership role in the target/active organization.
- **Workspace isolation:** expenses, budgets, receipts, invitations, activity, analytics, and notifications use scoped querysets. Dedicated multitenant tests verify cross-workspace denial.
- **CORS:** allowed origins come from environment settings. The custom workspace header is explicitly allowed.
- **CSRF:** Django CSRF middleware remains enabled. API authentication uses Bearer headers and Axios has `withCredentials: false`, so browser cookie authentication is not relied upon for REST calls.
- **Uploads:** receipt size and MIME/extension validation occur before AI processing; Pillow verifies the actual image.
- **Secrets:** Django secret, JWT signing key, email password, Google configuration, and Gemini key belong in `.env` and must never be committed or sent to React.

One honest current limitation: although the backend issues a refresh token and exposes `/api/auth/refresh/`, `AuthContext.jsx` currently persists only the access token and does not automatically refresh it. When the short-lived access token expires, the response interceptor signs the user out. This is a future security/usability improvement, not something to claim as already complete.

## 10. Testing and validation

The backend has tests in `users`, `organizations`, `expenses`, `receipts`, `budgets`, `analytics`, `notifications`, `activity_logs`, and the project package. Coverage includes:

- registration, email delivery rollback, login throttling, hashed tokens, password reset, and optional 2FA;
- organization creation/switching, multiple memberships, invitations, owner rules, and last-owner protection;
- cross-workspace access denial for expenses, budgets, receipts, invitations, activity, and notifications;
- staff/owner expense states, immutable status fields, approvals/rejections, resubmission, and receipt metadata;
- Gemini upload success/failure and parsing/normalization;
- budget dates, overlap rules, owner permissions, approved-only/category/range usage, and alert email behavior;
- approved-only analytics, staff scope, filtering, CSV safety, AI fallback, and anomalies;
- one end-to-end core business flow smoke test.

Validation performed on 2 July 2026:

- `python manage.py check`: **passed**, no Django system issues.
- `python manage.py test`: **147 tests passed** in about 87 seconds.
- `npm.cmd run build`: **passed**, 1,993 modules transformed.
- Build warning: the main JavaScript bundle is about 541 kB minified, so future route-level code splitting would improve initial loading.
- Environment warning: Python reported a `requests` dependency-version warning; tests still passed, but aligning those package versions would keep the environment clean.

No dedicated frontend unit-test command exists in `frontend/package.json`; current frontend validation is the successful Vite build plus backend/API tests.

## 11. Defense scripts

### One-minute introduction

“My project is Vyapar Margadarshan, a business expense management platform for small businesses and teams. It solves the problem of expenses being scattered across receipts, spreadsheets, and messages. An owner can create multiple workspaces, invite staff, define budgets, review staff expenses, and view approved-spending reports. Staff can submit expenses manually or scan receipts with Gemini AI, then follow approval or rejection and correct rejected entries. The frontend is built with React, Vite, and Tailwind, while the backend uses Django REST Framework, JWT authentication, and SQLite. Workspace membership and owner/staff permissions keep each organization's data separate. Only approved expenses affect official reports and budgets, which keeps the financial information reliable.”

### Three-minute explanation

“Vyapar Margadarshan is designed around a workspace. A user can belong to more than one organization and can have a different role in each one. Membership is stored separately from the user, which makes this flexible. The React frontend sends a JWT for identity and an organization header for the active workspace. Django verifies both the token and the membership before returning data.

The main workflow is expense control. When staff submit an expense, it becomes pending and the owners are notified. Owners review the details and receipt, then approve or reject it. If rejected, the reason is stored and the original staff member can correct and resubmit it. Owner-created expenses are approved automatically. The server controls the status fields, so a browser cannot directly mark its own expense approved.

For receipt scanning, the backend validates and compresses the image and sends it to Gemini Flash. Gemini extracts vendor, amount, date, category, notes, and confidence. The user reviews these values before creating an expense because AI can make mistakes.

Budgets can be overall or category-based and daily, weekly, monthly, or yearly. Their used amount is calculated from approved expenses in the same workspace and period. Reports also use only approved expenses and provide totals, trends, category/vendor breakdown, comparison, CSV export, and optional Gemini insights. If Gemini insights fail, the backend returns deterministic fallback observations.

Security is enforced by JWT authentication, role permissions, tenant-scoped querysets, rate limiting, account lockout, hashed security tokens, environment-based secrets, and upload validation. I validated the project with Django checks, a successful frontend build, and 147 passing backend tests.”

### Five-minute demonstration

1. **Landing/login (30 sec):** “The landing page presents the product. I will sign in as an owner. Authentication uses JWT, and the selected workspace is sent with each API request.”
2. **Workspace switcher (30 sec):** “This user can belong to multiple workspaces. Switching changes both the current role and all scoped data.”
3. **Dashboard (40 sec):** “The dashboard shows approved daily, weekly, and monthly spending, recent entries, categories, pending approvals, and budget progress.”
4. **Team (40 sec):** “An owner can invite staff by email and manage roles. Staff can view the team but cannot use these controls.”
5. **Staff expense/AI scan (60 sec):** “As staff, I can add an expense manually or upload a receipt. Gemini suggests the fields, but I verify them before submission. The new staff expense is pending.”
6. **Approval (50 sec):** “Back as owner, I open Approvals, inspect the receipt, and approve or reject. Rejection stores a reason. Editing a rejected expense resubmits it automatically.”
7. **Budgets (35 sec):** “The approved expense contributes to matching budgets. Pending and rejected amounts do not distort the usage.”
8. **Reports/AI (45 sec):** “I filter approved expenses, show trends and breakdowns, export CSV, then generate AI insights. The AI receives a controlled summary and has a fallback.”
9. **Close (10 sec):** “This demonstrates the complete controlled flow from team membership and capture to approval, budget monitoring, and analysis.”

### Feature-by-feature speaking cues

- **Workspace:** “The tenant boundary of the application.”
- **Membership:** “A many-to-many link with a role per organization.”
- **JWT:** “Proves who the caller is; membership proves what workspace they may access.”
- **Approval:** “Converts a submitted record into official business spending.”
- **Receipt AI:** “Reduces typing but keeps a human verification step.”
- **Budget:** “A date/category limit calculated from approved transactions.”
- **Report:** “A live calculation, not a duplicated stored table.”
- **Activity log:** “Explains who performed important workspace actions and when.”
- **Admin:** “Platform maintenance interface, separate from normal owner features.”

## 12. Likely viva questions and answers

### Why did you choose Django REST Framework?

It provides mature authentication, serializers, permissions, validation, ORM integration, and test utilities. This fits a data-heavy business system and keeps important rules on the server.

### Why React?

React makes interactive tables, filters, modals, workspace switching, dashboards, and role-based views easier to organize into reusable components.

### What makes the project multi-tenant?

Organization is the tenant. Membership authorizes a user for that tenant, the active organization identifies the current context, and backend querysets filter records by both membership and organization.

### Why not store the role directly on User?

A user may be an owner in one workspace and staff in another. The role therefore belongs to `Membership`, not globally to `User`.

### How do you prevent a user from changing the organization header?

The header is only a request for context. The backend accepts it only when a membership exists for the authenticated user. Otherwise it falls back to a valid context or scoped queries deny access.

### Can staff approve their own expense by changing the request?

No. Status and reviewer fields are read-only in the serializer, and decision endpoints require owner membership. Tests also verify that staff cannot approve/reject.

### Why are only approved expenses used?

Budgets and reports represent accepted business spending. Pending entries are undecided and rejected entries are not accepted, so including them would produce incorrect figures.

### How is a rejected expense resubmitted?

The original submitter edits it. The backend detects the rejected state, changes it to pending, clears old decision metadata, logs the event, and notifies owners.

### How does receipt AI work technically?

The backend validates and compresses the image, calls Gemini with a strict JSON prompt, parses and normalizes the response, stores scan metadata, and lets the user verify it before creating the linked expense.

### What if Gemini returns bad JSON or is unavailable?

Receipt processing records a failed status and shows a safe message, allowing manual entry. Expense insights use a deterministic fallback generated from backend metrics.

### Is AI allowed to approve an expense?

No. AI only assists data extraction and explanation. A human owner controls staff approval.

### How are budget dates calculated?

Daily ends the same day, weekly spans seven days, monthly derives the next-month boundary, and yearly derives the next-year boundary. Custom start dates are supported and end dates are inclusive.

### Is there a Report model?

No. Reports are calculated on demand from approved expenses. This avoids duplicated or stale report data.

### What is the difference between Django admin and an organization owner?

An owner manages one business workspace through the React app. Django admin is a platform-maintenance interface with broader system-level visibility.

### How did you test tenant security?

Dedicated multi-tenant tests attempt cross-organization access to expense, budget, receipt, invitation, notification, and activity resources. The current full suite has 147 passing tests.

### Does the frontend automatically refresh JWT access tokens?

Not currently. The backend supports refresh and rotation, but the frontend persists only the access token and logs out on 401. Automatic refresh with safer refresh-token storage is a planned improvement.

## 13. Limitations and future enhancements

- Add automatic access-token refresh with a carefully secured refresh-token strategy.
- Add frontend unit, component, accessibility, and end-to-end browser tests.
- Split large React routes into lazy-loaded chunks to reduce the current main bundle.
- Improve mobile receipt capture, cropping, glare correction, and duplicate detection.
- Extract and verify receipt line items; the database supports line-item JSON but the current prompt does not populate it.
- Add attachment history and multiple documents per expense if business requirements grow.
- Add richer accounting features such as recurring expenses, tax/VAT summaries, reimbursement/payment state, and accounting exports.
- Add configurable approval levels for larger teams while keeping the current owner/staff model simple.
- Add more currencies and explicit exchange-rate handling; current values are displayed in a chosen currency but are not automatically converted.
- Expand notification preferences and real-time updates.
- Improve AI evaluation with a labeled receipt dataset and measured field-level accuracy.
- Align the local Python HTTP dependency versions to remove the current warning.

## Final sentence for the defense

“The main strength of Vyapar Margadarshan is not only recording expenses; it creates a controlled, workspace-aware journey from capture and human approval to reliable budget monitoring and reporting, with AI used as an assistant rather than as the authority.”
