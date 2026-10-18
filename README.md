# ServiceDesk Leads

A single-business lead and follow-up application for a small air-conditioning installation and maintenance company.

**Current status: Milestone 2 complete — first usable workflow.** Customers can submit a service inquiry and receive a reference. Staff can log in, view a paginated list of all leads, open inquiry details, and log out. Submissions have transactional duplicate protection, CSRF protection, validation, and database-backed rate limits. This is a local development build; hosted demo and deployment are still planned.

## Build progress

| Milestone | Status | Result |
| --- | --- | --- |
| 1. Local foundation and contracts | Complete | Django, PostgreSQL, Vite, configuration, migrations, and readiness check |
| 2. Accounts and inquiry intake | Complete | Public inquiry form, staff sessions, protected lead list/detail, validation, and duplicate protection |
| 3. Lead ownership and sales workflow | Next | Claim and assign leads, record contact and quotes, change stages, add notes, and show activity history |
| 4. Follow-up tasks | Todo | Schedule, reschedule, complete, and cancel follow-ups; identify overdue work |
| 5. Working interface and dashboard | Todo | Search and filters, pipeline, responsive workflow screens, and business metrics |
| 6. Reliable external integration | Todo | Simulated and live email adapters, recorded attempts, safe retry, and delivery events |
| 7. Verification and hosted demo | Todo | Critical browser checks, synthetic demo data, deployment, backup restore, and rollback rehearsal |
| 8. Portfolio packaging | Todo | Screenshots, architecture overview, walkthrough, and evidence-based case study |

Update this table and the current-status paragraph when a milestone is completed. The detailed scope, estimates, dependencies, and acceptance checks are in the [implementation plan](docs/implementation-plan.md).

### What the current build does

- Accepts a fictional customer inquiry with contact, service, and request details.
- Gives the customer a reference and safely recognizes a retry of the same submission.
- Lets staff log in, see all submitted leads, and open a lead's details.
- Protects staff screens and API data with Django sessions and CSRF checks.
- Validates requests, limits repeated public requests, and reports service health.

The current build does not yet assign or edit leads, record notes or follow-up tasks, show a dashboard, or send integration alerts. Calls, messages, and quotes remain manual in the planned MVP.

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
.\.venv\Scripts\python.exe backend\manage.py test accounts crm operations config.tests
.\.venv\Scripts\python.exe -m ruff check backend scripts
.\.venv\Scripts\python.exe -m ruff format backend scripts --check
Set-Location frontend
npm.cmd run build
npm.cmd run format:check
```

The test command names the backend apps explicitly because running discovery from the repository root can otherwise report zero tests. Tests create and remove `test_lead_followup`; they do not use or erase the ordinary development database. Keep the local database running during these checks.

`npm run build` runs strict TypeScript checking before producing compiled frontend assets. It verifies buildability, not complete browser workflows. See [the testing guide](docs/testing.md) for what each check proves and how to exercise failure/recovery.

## Where to look

- `backend/config/`: environment settings, middleware, routing, and API error handling.
- `backend/accounts/`: users, CSRF-protected sessions, and local account setup.
- `backend/crm/`: lead/history models, transactional public intake, and protected read APIs.
- `backend/operations/`: readiness and shared rate limits.
- `frontend/src/app/`: application shell and route protection; `features/` contains inquiry, login, and lead screens.
- `compose.yaml`: local PostgreSQL only.
- [Build plan](docs/implementation-plan.md), [architecture](docs/architecture.md), [API contract](docs/api.md), and [technical decisions](docs/decisions.md).

Other skeleton files remain empty until their milestone needs them. Deployment scripts and production asset hosting are not implemented yet; no infrastructure has been deployed.

## Troubleshooting

- **Docker engine unavailable:** start Docker Desktop and wait for it to become ready.
- **Database unavailable:** check `docker compose ps`, the `.env` port/credentials, and `docker compose logs --tail 30 db`. Avoid sharing logs or environment files containing secrets.
- **Frontend cannot reach the API:** ensure Django is running at `127.0.0.1:8001`; Vite forwards `/api` there.
- **A port is occupied:** Vite deliberately fails instead of silently moving to a different port. Stop the conflicting process or change configuration intentionally.
- **Zero tests discovered:** use the explicit app labels in the command above.
- **Permission/network failures in Codex's sandbox:** package downloads, localhost connections, and development servers may require host execution approval. Do not weaken firewall settings to work around them.

## Test the working flow

1. Submit a fictional inquiry. Name, service, one contact method, and privacy acknowledgement are required.
2. Record the confirmation reference. No email is sent in this milestone.
3. Log in using a local account and open the saved inquiry.
4. Refresh the page to check the session persists; log out to check private pages redirect to login.
5. If submission cannot be confirmed, retry the same inquiry. The screen locks its details and reuses the submission key to avoid accidental duplicates. Only the opaque key is retained in session storage; customer fields are kept in component memory.

See [Milestone 2 testing notes](docs/milestone-2.md) for results, limits, and the next build boundary.

## Next milestone

Milestone 3: let staff claim unassigned leads and work on leads assigned to them; let admins assign or reassign leads. Add contact recording, quote and stage changes, notes, and activity history. Staff will continue to view all active leads but can change only their own assigned leads. See the [Milestone 3 acceptance checks](docs/implementation-plan.md#milestone-3--lead-ownership-and-sales-workflow).
