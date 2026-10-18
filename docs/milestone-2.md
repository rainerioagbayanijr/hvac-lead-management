# Milestone 2 — inquiry intake and staff viewing

Implemented and verified locally on 18 October 2026. No external deployment or email sending occurred.

## What this version does

1. A prospective customer submits a service inquiry and receives a confirmation reference after commit.
2. Missing or invalid information produces field errors without clearing the form.
3. Repeating the same submission key and normalized payload returns the existing reference. Reusing a key with changed details returns a conflict.
4. Staff log in through Django sessions, read the paginated team lead list, and open contact/service details with the creation history.
5. Login survives a page reload. Logout invalidates access; anonymous visitors are redirected away from private screens and denied by the API itself.

The app does not yet assign ownership, edit records, record contact, move stages, schedule tasks, show business metrics, or send alerts. Those controls are not presented as working features.

## How to try it

Keep Docker Desktop, project PostgreSQL, Django on `127.0.0.1:8001`, and Vite on `127.0.0.1:5173` running. Follow the README setup if needed.

- Public form: `http://127.0.0.1:5173/`.
- Staff login: `http://127.0.0.1:5173/login`.
- Local credentials: ignored `.local-accounts.md`. Do not commit or share it.
- Optional local setup: `python backend/manage.py create_dev_accounts`, using the project virtual environment. This never resets existing notes/passwords and is guarded against production or remote databases.
- Only use fictional customer details. The browser checks left Avery Demo and Jordan Demo inquiries as working examples; neither triggers email.

The development admin is a local technical superuser. It is not suitable for shared public-demo access. Public demo sessions and periodic resets belong to Milestone 7.

## What was tested

Run from the repository root with PostgreSQL running:

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

The backend suite passes **72 tests**, including the earlier foundation checks:

- CSRF required for anonymous login and inquiry submission, plus logout.
- Session and CSRF rotation on login; fixed expiry; session deletion on logout.
- Generic failed/inactive login errors; deactivated users lose existing access.
- Anonymous list/detail access rejected; active staff may read other owners' leads.
- Creation is New/unassigned/website, with one initial activity event.
- Idempotent replay, changed-payload conflicts, and preserved original identity after ordinary record edits.
- Actual simultaneous PostgreSQL submissions: identical requests produce one lead/event; different payloads under one key have one winner/conflict.
- Activity-write failure rolls back the new lead.
- Phone-only contact, field/length validation, honeypot, privileged-field rejection, malformed JSON, and oversized bodies.
- Shared rate limits, Retry-After, window rollover, untrusted forwarding headers, and concurrent limit enforcement.
- Pagination, protected read-only endpoints, and safe missing-record errors.
- Local-account setup production/remote-database guards, idempotence, and no passwords printed to command output.

Tests use a fresh temporary PostgreSQL test database, not the ordinary development records. They do not use SQLite.

Django configuration/migration-drift checks, Ruff lint/format checks, strict TypeScript checking, Vite build, and Prettier checks all passed. Secrets and local account notes were confirmed ignored by Git. CI wiring and production deployment checks remain scheduled for Milestone 7.

## Browser verification

- Entered a name without contact information: received a field error while name/privacy state stayed filled.
- Submitted Avery Demo with fictional details: confirmation reference appeared; the saved lead and creation event were visible after login.
- Verified failed login messaging, successful staff login, persistence after reload, logout, and private-page redirection.
- At a 390px viewport the public form had no horizontal overflow.
- The mobile lead cards and 1280px desktop table both showed the saved inquiries without horizontal overflow. Screenshots are in `screenshots/milestone-2-leads.png` and `screenshots/milestone-2-detail.png`.
- Stopped only this project's backend during a Jordan Demo submission attempt. The UI showed an uncertain outcome, preserved values, locked edits, and offered retry with the same key. After restart, retry succeeded. This was a server-unreachable check; replay-after-commit behavior is covered separately by the backend replay/race tests.

## Bugs found and fixed

- Django's original Http404 was converted internally by DRF but missed by the custom error formatter. Missing records now return the agreed `not_found` code.
- A delayed initial session read could overwrite successful login state. Successful login/logout now cancel old session reads.
- Read requests with component cancellation also need a timeout. Both cancellation signals are now handled without leaving a permanent loading screen.

## Operational limits

This is a local development build. Production hosting/static packaging, complete workflow authorization, reverse-proxy configuration, scheduled rate-bucket cleanup, demo reset, backup rehearsal, and provider integration are still future work.

The rate limits use fixed windows, not rolling windows, and are basic application abuse controls rather than complete DDoS protection. Local proxy requests share the localhost IP; that is expected for local testing.

Only the opaque inquiry key is saved in browser session storage. Form contents stay in component memory. On uncertain outcomes, retry without changing details. Refreshing the page loses typed fields; the retained key still prevents a changed payload from silently overwriting an earlier accepted inquiry.

## Next milestone

Milestone 3 adds ownership/claims and write permissions first. Then it adds contact recording, quote/stage changes, notes, and transactional activity events. Manual inquiry entry belongs with those staff actions.
