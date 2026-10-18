# Implementation plan

Status: Milestones 1–4 are implemented. Milestone 4 focused checks and local browser verification are recorded in `milestone-4.md`.

## Goal and constraints

Build a portfolio-ready, single-business CRM for an air-conditioning company in approximately two weeks at 20–25 hours per week. Budget 46 hours of planned work and 4 hours of contingency. This is an aggressive upper-bound schedule; apply the fallback scope if the available budget is closer to 40 hours.

Keep the agreed stack: Python/Django, Django REST Framework, PostgreSQL, React/TypeScript/Vite, Tailwind, and Git. Use a modular monolith, Django sessions, and same-origin hosting. Use PostgreSQL-backed integration executions and a scheduled Django command rather than Celery or Redis. No uploads, billing, tenancy, AI scoring, campaigns, or mobile app.

Build small, working flows across the database, API, and interface. Add focused tests with the behavior they verify. Do not build every backend endpoint before validating a usable screen.

The repository began as empty skeleton files. Milestones 1 and 2 now contain the local foundation and first usable workflow; future files remain placeholders. Populate each file when its milestone needs it. Generate dependency lockfiles with the package tools instead of writing pretend lockfiles. Keep future files untouched until needed.

## What to build first

First establish the local foundation, then complete this working flow:

1. A customer submits an inquiry through the public form.
2. The server validates and stores one New, unassigned lead in PostgreSQL.
3. Retrying the same submission returns the original reference.
4. An administrator logs in using a secure Django session.
5. The administrator sees the inquiry in a minimal lead list and detail screen.
6. An anonymous visitor cannot read those records.

This first flow proves the stack, database, authentication, CSRF handling, API errors, and frontend communication before adding workflow complexity. It should take about nine hours across milestones 1 and 2. Use a plain, readable interface at this stage; visual polish follows the working behavior.

## Ordered milestones

| Milestone | Estimate | Depends on | Reviewable result |
| --- | ---: | --- | --- |
| 1. Local foundation and contracts | 3h | Existing blueprint | Both development processes run; PostgreSQL connects; initial migrations and health check work |
| 2. Accounts and inquiry intake | 6h | 1 | Public form to protected lead list/detail, with sessions and duplicate protection |
| 3. Lead ownership and sales workflow | 7h | 2 | Claim, assign, contact, quote, close, notes, and activity history |
| 4. Follow-up tasks | 4h | 3 | Schedule, reschedule, complete, cancel, and highlight overdue work |
| 5. Working interface and dashboard | 8h | 3–4 | Responsive screens, filters, simple pipeline, and precisely calculated metrics |
| 6. Reliable external integration | 7h | 2–3 | Recorded email attempts, safe retry, fake/live adapters, and verified delivery events |
| 7. Verification and hosted demo | 8h | 4–6 | Critical checks pass; synthetic demo, deployment, and restore rehearsal complete |
| 8. Portfolio packaging | 3h | 7 | README, diagram, walkthrough, and evidence-based case study |
| Planned work | 46h | | |
| Contingency | 4h | | |

### Milestone 1 — local foundation and contracts

Build in this order:

1. Inspect available Python, Node, and PostgreSQL tools. Choose compatible versions and document prerequisites. Preserve the existing Git repository.
2. Populate the backend dependency/configuration files and create the development environment. Add only Django, DRF, and the PostgreSQL driver at first; add production and integration packages when needed.
3. Populate Django project settings, URL routing, and startup files. Separate local and production settings; read secrets from the environment.
4. Define the custom User model before the first migration, with admin/staff application roles. Use Django's existing password and session mechanisms.
5. Define the initial Lead model: contact details, service, source, stage, owner, receipt/creation/update timestamps, version, submission key, and immutable request fingerprint. Add the intake constraints needed now.
6. Create and apply the first migrations to local PostgreSQL. Use the same database engine in tests.
7. Establish a minimal readiness endpoint that checks database connectivity without exposing configuration.
8. Populate valid frontend configuration, a Vite entry point, Tailwind setup, and a minimal app shell. Configure the local API proxy.
9. Document the initial role policy and API error format. Add setup instructions and a safe environment example.

Acceptance checks:

- Django and Vite start locally using documented instructions.
- PostgreSQL is reachable; migrations apply to a fresh local database.
- The custom User model is configured before migration dependencies are established.
- A browser can reach the API through the frontend proxy.
- The readiness endpoint returns a minimal status and fails safely if the database is unavailable.
- No credentials are committed; the existing Git repository is preserved.

Learning checkpoint: explain the difference between a model, migration, API view, frontend screen, and environment setting.

### Milestone 2 — accounts and inquiry intake

Backend:

- Create development accounts using Django admin or a local management command; no public signup.
- Implement CSRF bootstrap, a CSRF-protected Django login view, session inspection, and logout. Protect authenticated DRF endpoints by default.
- Implement public intake through a transactional CRM service. Validate contact fields and required service details; force New stage, no owner, and website source on the server.
- Enforce a unique submission UUID and stored original request fingerprint. Same key/same payload returns the original reference; changed payload returns a conflict.
- Add shared database rate limits for login and public intake, request-size limits, and a honeypot.
- Implement a minimal protected list and detail endpoint. Only ordinary intake fields are writable.

Frontend:

- Build the inquiry form, success reference, login form, minimal lead list, and minimal detail page.
- Keep the submission key across uncertain outcomes. Preserve entered fields after validation or network errors.
- Handle unauthenticated sessions, CSRF errors, validation messages, loading, empty, and success states.

Acceptance checks:

- A submitted inquiry appears once in PostgreSQL and in the authenticated UI.
- Anonymous requests cannot list or read leads.
- Retrying after an uncertain response does not create another lead.
- A changed payload under an existing key is rejected.
- Client-supplied stage, owner, and source cannot override public intake policy.
- Login and anonymous intake explicitly enforce CSRF; logout invalidates the session.
- Concurrent duplicate submissions and rate-limit updates are tested against PostgreSQL.

Learning checkpoint: trace the request from React to validation, business service, database transaction, and response. Explain why browser button disabling is insufficient duplicate protection.

### Milestone 3 — lead ownership and sales workflow

- Staff read all active leads but mutate only their assigned leads. Staff can claim unassigned leads for themselves; admin can assign/reassign.
- Implement transactional actions with row locking and expected-version checks. A stale edit or losing concurrent claim receives a conflict.
- Add explicit contact recording, quote amount, stage changes, Won/Lost outcomes, and admin reopening.
- Use New → Contacted → Quoted → Won; allow any open stage to become Lost with a reason.
- Record first contact once; do not infer it from a note or alert.
- Add append-only notes with client submission keys and append-only activity history written in the same transaction as the action.
- Add manual inquiry entry with source tracking and a validated receipt timestamp.
- Keep Django admin from bypassing business rules through arbitrary record editing.

Acceptance checks: unauthorized changes fail on direct API requests and nested resources; simultaneous claims have one winner; notes retry safely; required quote/loss fields are enforced; state and history commit together; reopening preserves first contact and prior closure history.

Learning checkpoint: explain why frontend permissions are presentation only, and why business actions live in services instead of signals.

### Milestone 4 — follow-up tasks

- Add task creation, rescheduling, completion, and cancellation to lead detail and a team task list.
- Store timezone-aware instants; accept and display due times in Asia/Singapore.
- Compute overdue from pending status and due time compared with server time. No timer job is needed to mark a task overdue.
- Task ownership follows the lead owner, so admin reassignment immediately changes the responsible staff shown in task views.
- Cancel open tasks transactionally when a lead becomes Won or Lost; show this consequence before the stage action and record the count in activity history.
- Reopening does not silently revive cancelled tasks; staff schedule the next action explicitly.
- Use lead version checks and activity action keys for stale-update protection and safe retry.

Acceptance checks: timezone-aware due-time validation, owner/admin authorization, schedule/reschedule/complete/cancel, overdue filtering, safe action retry, and closure cancellation are covered by focused API tests. Browser walkthrough verifies task creation from a lead, task-list status filters, and updating a task.

Learning checkpoint: explain why overdue is a computed condition rather than a stored status requiring scheduled updates.

### Milestone 5 — working interface and dashboard

- Apply the agreed Tailwind colors, typography, spacing, and small reusable controls.
- Add lead search, filters, pagination, URL-persisted filters, and My/Unassigned/Overdue shortcuts.
- Add a simple pipeline with explicit stage controls; no drag-and-drop.
- Complete lead detail, notes/history, task list, and mobile layouts.
- Add admin archive/restore and CSV export with formula-injection protection.
- Implement current pipeline counts, open quoted value, cohort first-response median/coverage, awaiting contact, overdue tasks, and closure win rate.
- Distinguish current-state metrics from date-cohort metrics. Show date boundaries, sample sizes, and empty denominators.

Acceptance checks: dashboard fixtures have known expected values; filtered lists paginate consistently; read-only states are clear; keyboard access, contrast, mobile layouts, loading/error/empty/validation/success states are reviewed.

Learning checkpoint: explain each metric's timestamps and denominator, and why quoted value is not revenue.

### Milestone 6 — reliable external integration

- Add execution, attempt, and webhook receipt models.
- Extend the existing inquiry transaction to create one pending internal alert. Do not silently send alerts for historical leads when applying this change.
- Build the deterministic fake adapter first, followed by the Resend HTTP adapter.
- Use an immutable message/recipient and a unique provider idempotency key. Keep customer details out of alerts.
- Process due executions through a scheduled Django command with short database claims, expiring leases, explicit network timeouts, and bounded retries.
- Retry eligible temporary failures at approximately 1, 5, 15, and 60 minutes after prior failures, for at most five automatic attempts.
- Apply the agreed 23-hour safe retry cutoff from the first attempt. Unknown outcomes outside it require review.
- Verify raw-body webhook signatures with the signing secret; deduplicate provider events; account for early and out-of-order receipts.
- Keep API acceptance separate from delivery. Do not automatically retry bounces or complaints.
- Add admin history/retry controls and a simple alert outcome on lead detail.

Acceptance checks: timeout followed by same-key retry; permanent failure; duplicate and invalid webhooks; lease recovery; attempt exhaustion; expired safe window; early receipt; and worker freshness are tested. A private provider test verifies acceptance and delivery behavior. Public demo mode cannot send live email.

Learning checkpoint: explain the difference between accepted, delivered, failed, and uncertain; identify where duplicate prevention has a time limit.

### Milestone 7 — verification and hosted demo

- Run four Playwright scenarios: inquiry-to-follow-up, overdue task completion/rescheduling, staff permission denial, and simulated integration retry.
- Use PostgreSQL for backend checks. Use deterministic clocks and fake network responses for scheduling/retry tests.
- Run Python lint, TypeScript checks, frontend build, and required tests in CI.
- Review authorization, secrets, cookies, CSRF, rate limits, logs, export safety, and production settings.
- Implement synthetic seed data, restricted demo access, server-enforced simulated integration, and guarded daily reset at 00:00 Singapore time.
- Populate deployment configuration only now. Build the React output into the Django release and exclude API/admin/webhook/health paths from SPA fallback routing.
- Prepare one paid Render web service, paid PostgreSQL, and scheduled work, with separate demo and production configuration.
- Verify health, cron freshness, session behavior, and the full demo flow after deployment.
- Perform a backup restore rehearsal into a separate database. Pause and reconcile integrations before resuming work after recovery.
- Document rollback to a prior application release and use backward-compatible migrations.

Acceptance checks: required checks pass; mobile and keyboard review complete; hosted demo contains only synthetic seed data; real sends are blocked in demo; reset is guarded from production; restore and rollback procedures are documented and exercised where applicable.

Learning checkpoint: locate a failure using a request/execution ID, explain how to restore data, and explain why restoring a database can revive old pending alerts.

### Milestone 8 — portfolio packaging

- Finish README with business problem, screenshots, setup, architecture, decisions, checks, limitations, and demo access.
- Save the architecture diagram and brief explanation of the reliable integration flow.
- Record a two-minute walkthrough of intake, ownership, follow-up, reporting, and failed-alert retry.
- Write a business case study separating demonstrated technical behavior from proposed customer benefits.
- Measure synthetic-data performance and record the environment, dataset, and procedure.
- Prepare a pilot measurement plan for actual response times, missed follow-ups, and conversion. Do not claim improvement without customer evidence.

Acceptance checks: a reviewer can launch the project from instructions, navigate the demo, understand the main tradeoffs, and distinguish simulated results from live-provider verification and real customer outcomes.

## Time and scope checkpoints

- End of approximately hour 9: intake and authenticated lead viewing work.
- End of approximately hour 20: ownership, sales workflow, and tasks work. Investigate and reduce scope if this is not true.
- Around hour 28: choose presentation/convenience cuts before starting extras.
- Reserve the final eight verification/deployment hours; do not consume them with stretch features.
- Use the four-hour buffer for actual integration/setup failures and learning needs, not new features.

For a 40-hour budget:

1. Replace pipeline columns with a stage-grouped list.
2. Use dashboard cards and a simple table.
3. Keep integration settings in environment configuration while retaining execution history and safe retry.
4. Export active leads without elaborate export options.
5. Keep all stretch features out.

If credentials are unavailable, demonstrate the clearly labeled fake adapter and document live setup. Do not claim the external integration has been verified live. Keep authorization, idempotency, task correctness, retry safety, and meaningful tests in every scope version.

## Working method

- Implement one milestone in small reviewable changes.
- Inspect code and run relevant checks before moving on.
- Keep business rules in Python; keep frontend decisions about display and interaction.
- Add dependencies only when the milestone requires them.
- Update documentation when a decision changes.
- Before accepting a milestone, explain its authorization, transaction boundaries, failure behavior, tests, and diagnostic trail.
- No stretch work until core behavior and its verification are complete.

Next implementation action: milestone 3, beginning with transactional lead claims/assignment and per-lead mutation permissions, followed by contact/stage actions and notes.
