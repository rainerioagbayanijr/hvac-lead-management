# ServiceDesk Leads

A single-business lead and follow-up application for a small air-conditioning installation and maintenance company.

**Current status: application milestones 1–8 are implemented and verified locally.** The project includes customer intake, staff ownership and sales stages, follow-ups, pipeline and dashboard reporting, lead archive/export, a recorded email integration with safe retry, synthetic demo data, CI/browser workflows, and a Render deployment blueprint. The public hosted demo has not been provisioned; live Resend delivery has not been verified because provider credentials are not configured.

## Build progress

| Milestone | Status | Result |
| --- | --- | --- |
| 1. Local foundation and contracts | Complete | Django, PostgreSQL, Vite, configuration, migrations, and readiness check |
| 2. Accounts and inquiry intake | Complete | Public inquiry form, staff sessions, protected lead list/detail, validation, and duplicate protection |
| 3. Lead ownership and sales workflow | Complete | Claim and assign leads, record contact and quotes, change stages, add notes, and show activity history |
| 4. Follow-up tasks | Complete | Schedule, reschedule, complete, and cancel tasks; identify overdue work |
| 5. Working interface and dashboard | Complete | Search/filters, pipeline, metrics, archive/restore, and safe CSV export |
| 6. Reliable external integration | Complete | Fake and Resend adapters, recorded attempts, retry leases, and signed/deduplicated webhooks |
| 7. Verification and demo readiness | Complete locally | Synthetic accounts/data, guarded reset, four browser workflows, CI, and Render configuration; hosted rollout and restore rehearsal await an account |
| 8. Portfolio packaging | Complete as source assets | Architecture, decisions, setup, walkthrough script, deployment guide, and evidence-based case-study draft |

Update this table and the current-status paragraph when a milestone is completed. The detailed scope, estimates, dependencies, and acceptance checks are in the [implementation plan](docs/implementation-plan.md).

### What the current build does

- Accepts a fictional customer inquiry with contact, service, and request details.
- Gives the customer a reference and safely recognizes a retry of the same submission.
- Lets staff log in, see all submitted leads, and open a lead's details.
- Lets staff claim unassigned leads and change only their assigned leads; admins can assign, reassign, and reopen.
- Records manual inquiries, customer contact, first response, SGD quotes, Won/Lost outcomes, internal notes, and dated history.
- Lets a lead owner or admin schedule, reschedule, complete, and cancel follow-up tasks; task changes appear in activity history.
- Shows open, completed, and cancelled follow-ups; overdue status is calculated from the due time and current time.
- Cancels open follow-ups when a lead is marked Won or Lost and records the cancellation count in lead history.
- Searches and filters the team’s leads; groups the pipeline by stage and shows response, quote, win, and overdue follow-up metrics.
- Lets admins archive and restore leads, and export up to 10,000 filtered active/archived leads to formula-safe CSV.
- Queues one internal email alert per accepted public inquiry and records provider attempts, delivery webhooks, failures, and safe retries.
- Uses a fake-only mode for the public synthetic demo; email is never sent in demo mode.
- Seeds and resets synthetic leads, follow-ups, accounts, and simulated email history with guarded management commands.
- Protects staff screens and API data with Django sessions and CSRF checks.
- Validates requests, limits repeated public requests, and reports service health.

The application does not make calls, send customer marketing messages, or generate quotes; staff perform those actions manually. Live Resend delivery and a hosted public demo still require account setup.

The [deployment guide](docs/deployment.md), [architecture](docs/architecture.md), [two-minute walkthrough script](docs/walkthrough.md), and [business case study](docs/case-study.md) describe the current implementation and its verification limits.

## Local stack

- Python 3.13; Django 5.2 LTS; Django REST Framework.
- PostgreSQL 17, running in a dedicated local Docker container.
- Node 22.12+ within the 22.x line (or another version supported by the pinned Vite release), React, TypeScript, Vite, and Tailwind.
- Django database-backed sessions. React accesses `/api/` through Vite's local proxy.

Docker is used only for the development database. Django and Vite run as ordinary local processes. This does not add Docker, Redis, or a queue to the production architecture.

## First-time setup on Windows

Run commands from the repository root unless a different directory is shown. Install Python 3.13, a compatible Node version, and Docker Desktop first. Start Docker Desktop before starting the database.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
.\.venv\Scripts\python.exe scripts\create-local-env.py
docker compose up -d --wait db
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py create_dev_accounts
Set-Location frontend
npm.cmd ci
Set-Location ..
```

The environment helper generates unique local credentials in `.env` and will not overwrite an existing file. `.env` is ignored by Git. The example file documents variable names without real credentials.

The database is bound to `127.0.0.1:55432` and uses its own persistent Docker volume. If this port is occupied, change `POSTGRES_PORT` in `.env` before starting the container. Do not reuse an unrelated application's database.

The container's development database user can create the temporary databases needed by Django tests. Production will use a separate restricted runtime role. Changing the password in `.env` does not change an already initialized PostgreSQL volume; update credentials inside PostgreSQL deliberately if needed.

## Start the app

Terminal 1, repository root:

```powershell
.\.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8001
```

Terminal 2:

```powershell
Set-Location frontend
npm.cmd run dev
```

Open [the local inquiry form](http://127.0.0.1:5173/). Submit fictional details, then use [staff login](http://127.0.0.1:5173/login) to view the saved lead. Generated local usernames/passwords are in ignored `.local-accounts.md`; keep that file private. The setup command never overwrites existing account notes/passwords and refuses nonlocal databases or production settings. The local admin is a technical superuser for development, not a public-demo account.

The backend uses port **8001** because another application occupies 8000 on this machine. Vite proxies `/api` to 8001. The database-aware hosting readiness endpoint is [http://127.0.0.1:8001/health/](http://127.0.0.1:8001/health/). To create additional accounts, the local owner can use Django admin at `/admin/` on the backend.

Use Ctrl+C to stop development servers. Stop the project database without deleting its data:

```powershell
docker compose stop db
```

Start it again with `docker compose up -d --wait db`. Do not use volume-deletion commands as a routine restart.

## Run the checks

From the repository root:

```powershell
.\.venv\Scripts\python.exe backend\manage.py check
.\.venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe backend\manage.py test accounts crm integrations operations config.tests
.\.venv\Scripts\python.exe -m ruff check backend scripts
.\.venv\Scripts\python.exe -m ruff format backend scripts --check
Set-Location frontend
npm.cmd run build
npm.cmd run format:check
```

The test command names the backend apps explicitly because running discovery from the repository root can otherwise report zero tests. Tests create and remove `test_lead_followup`; they do not use or erase the ordinary development database. Keep the local database running during these checks.

`npm run build` runs strict TypeScript checking before producing compiled frontend assets. CI also runs four Playwright browser journeys against a throwaway PostgreSQL database. To run them locally, seed only a synthetic database with `DEMO_MODE=true` and configured `DEMO_*_PASSWORD` values, then set `E2E_ADMIN_USERNAME`, `E2E_ADMIN_PASSWORD`, `E2E_STAFF_USERNAME`, and `E2E_STAFF_PASSWORD` before `npm run test:e2e` from `frontend`. The Playwright server uses ports 8001 and 5174 by default. See [the testing guide](docs/testing.md) for failure cases and what each check proves.

## Where to look

- `backend/config/`: environment settings, middleware, routing, and API error handling.
- `backend/accounts/`: users, CSRF-protected sessions, and local account setup.
- `backend/crm/`: lead/history models, transactional public intake, and protected read APIs.
- `backend/crm/tasks.py`: transactional follow-up task rules; task API endpoints are in `backend/crm/api/`.
- `backend/integrations/`: fake/Resend adapters, durable attempts, leases, and verified webhook handling.
- `frontend/src/features/tasks/`: team follow-up list; task creation and history are on each lead detail page.
- `backend/operations/`: readiness, request limits, guarded demo seed/reset, and operational commands.
- `frontend/src/app/`: application shell and route protection; `features/` contains dashboard, inquiry, login, lead, integration, and task screens.
- `deploy/`: multi-stage Docker image and Render demo Blueprint.
- `frontend/e2e/`: critical customer/staff/admin browser workflows.
- `compose.yaml`: local PostgreSQL only.
- [Build plan](docs/implementation-plan.md), [architecture](docs/architecture.md), [API contract](docs/api.md), and [technical decisions](docs/decisions.md).

All source milestones are implemented. Hosted demo provisioning, live Resend verification, hosted backup restoration, and a recorded walkthrough remain account-dependent work; no cloud resources have been created. See the [deployment guide](docs/deployment.md).

## Troubleshooting

- **Docker engine unavailable:** start Docker Desktop and wait for it to become ready.
- **Database unavailable:** check `docker compose ps`, the `.env` port/credentials, and `docker compose logs --tail 30 db`. Avoid sharing logs or environment files containing secrets.
- **Frontend cannot reach the API:** ensure Django is running at `127.0.0.1:8001`; Vite forwards `/api` there.
- **A port is occupied:** Vite deliberately fails instead of silently moving to a different port. Stop the conflicting process or change configuration intentionally.
- **Zero tests discovered:** use the explicit app labels in the command above.
- **Permission/network failures in Codex's sandbox:** package downloads, localhost connections, and development servers may require host execution approval. Do not weaken firewall settings to work around them.

## Test the working flow

1. Submit a fictional inquiry. Name, service, one contact method, and privacy acknowledgment are required.
2. Sign in as staff/admin, claim or assign the inquiry, record contact or a quote, add an internal note, and schedule a follow-up.
3. Open the dashboard and pipeline; use list filters to find the lead and review overdue work.
4. Open integration history as admin. The default local adapter is fake; no external email is sent unless Resend is explicitly configured.
5. If a response is lost, retry the same inquiry. The server's submission key prevents a duplicate lead and alert execution.

The hosted demo uses synthetic records and disables public intake. Live provider delivery and business outcomes have not been verified. See [Milestone 5](docs/milestone-5.md), [Milestone 6](docs/milestone-6.md), [Milestone 7](docs/milestone-7.md), and [Milestone 8](docs/milestone-8.md) for evidence and limits.

## Remaining account setup

Create the Render workspace, review the current estimated costs, provide demo credentials as provider secrets, and apply `deploy/render.yaml`. Then complete hosted health/browser checks, a restore rehearsal, and the walkthrough recording. Configure Resend only in a separate business environment. The [deployment guide](docs/deployment.md) gives the checklist and rollback steps.
