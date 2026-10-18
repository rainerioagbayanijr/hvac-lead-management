# Testing and learning guide — Milestone 1

This file preserves the Milestone 1 verification record. For the current workflow, see [Milestone 3 testing](milestone-3.md) and [Milestone 2 testing](milestone-2.md). The current backend development port is 8001; the connection-card preview below has been replaced by the real inquiry form.

## Verification results — 13 October 2026

- 35 automated backend tests passed against PostgreSQL 17.11, with migrations applied to a fresh temporary test database.
- Django system checks passed; no migration drift was detected.
- Ruff lint and formatting checks passed; installed Python dependencies passed `pip check`.
- Strict TypeScript checking and the Vite production build passed. npm installation reported zero known dependency vulnerabilities at installation time.
- Browser checks passed for real API connection, the check-again control, actual database outage (503), and recovery after restart.
- Layouts were inspected at 390px and 1280px viewports; neither had horizontal overflow. Keyboard activation of the skip link worked.
- Local secrets, the virtual environment, npm dependencies, and build output were confirmed ignored by Git.

These are local foundation results, not production certification or evidence that later business workflows exist.

## What was built and why

1. Settings separate local and production behavior, with secrets outside source control.
2. Migrations create the custom user before other apps depend on it and create the initial lead table.
3. PostgreSQL constraints protect basic record validity even if an entry point forgets Python validation.
4. DRF defaults deny anonymous access; per-lead permissions come later.
5. Readiness queries the real database. The React screen reaches it through Vite's API proxy.

A model describes records. A migration changes their database schema. A view handles a request. A service will coordinate permissions and business changes. A React component presents the result. These are distinct responsibilities.

## Automated checks

Run from the repository root with PostgreSQL running:

```powershell
.\.venv\Scripts\python.exe backend\manage.py check
.\.venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe backend\manage.py test accounts crm operations config.tests
.\.venv\Scripts\python.exe -m ruff check backend scripts
.\.venv\Scripts\python.exe -m ruff format backend scripts --check
Set-Location frontend
npm.cmd run build
```

| Check | What it establishes |
| --- | --- |
| Django system check | Settings, model relationships, and admin configuration are consistent |
| Migration drift check | Checked-in migrations match the model definitions |
| Fresh PostgreSQL test database | Initial migrations can build an isolated schema without relying on existing local tables |
| User tests | Passwords are hashed; regular users default to application staff; superusers use application admin |
| API access tests | Anonymous/inactive requests are denied; Django sessions authenticate an active user |
| Lead tests | Contact/name/choice/version constraints; unique submission keys and valid fingerprints; shared contacts allowed; receipt validation; identity preservation; protected user references |
| Health tests | Real query success; sanitized 503; no caching; mutating requests denied; trusted request references |
| Error contract tests | Field messages retained; unexpected exceptions return generic JSON without private details |
| Production settings tests | Debug disabled; cookies secure; missing secret/wildcard hosts/unencrypted DB configuration rejected |
| Ruff | Python static checks and consistent formatting |
| Frontend build | Strict TypeScript check plus successful Vite/Tailwind compilation |

Database tests create `test_lead_followup`, apply migrations from scratch, and remove that temporary database afterwards. They never intentionally mutate ordinary development records.

Tests include failure cases, not only successful construction. Expected 400/403/405/500/503 messages in test logs do not indicate suite failure; read the final test summary and exit code.

## Browser smoke checks

With Django and Vite running:

1. Open `http://127.0.0.1:5173/` and confirm “Django and PostgreSQL are connected.”
2. Use “Check again” and confirm that the control displays a loading state and recovers.
3. Test a narrow viewport: text/cards stack without horizontal scrolling.
4. Use the keyboard to reach the skip link and connection button; verify visible focus.
5. Temporarily stop only the project database with `docker compose stop db`.
6. Check `/api/v1/health/` through the frontend: expect 503 and only `{"status":"unavailable"}`.
7. Use “Check again”: expect the database-unavailable message.
8. Restart with `docker compose up -d --wait db`; use “Check again” and confirm recovery.

Restore the database even if a smoke check fails. Do not stop unrelated containers or delete the volume. HTTP checks and a TypeScript build alone do not prove the rendered UI behaves correctly.

## Bugs caught during implementation

- Normalizing email inside `Model.clean()` was too late: Django field validation runs first. Normalization now occurs before field validation, and its regression test is retained.
- Test discovery from the repository root initially found zero tests. The documented command names backend apps explicitly, so the intended suite actually runs.
- A Vite process started inside the execution sandbox was inaccessible from the host browser. Restarting it with host permission fixed access without changing firewall rules or exposing the server beyond localhost.

## Limits of this milestone's evidence

These checks do not prove customer intake, staff login forms, per-lead mutation permissions, concurrent claims, task scheduling, or provider retry correctness. Those flows do not exist yet. Add their tests in their implementation milestones.

Before moving on, explain why contact details can repeat across leads while a public submission key cannot, why `save()` is not complete validation, why role differs from `is_staff`, and why an HTTP 200 page does not prove its database works.
