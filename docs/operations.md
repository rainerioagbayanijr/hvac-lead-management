# Operations and data handling

## Secrets, cookies, and logging

Keep `.env`, demo passwords, Django secret keys, Resend API keys, webhook signing secrets, and database URLs in the hosting secret store. The committed `.env.example` contains placeholders only. Rotate provider secrets through the provider dashboard and deploy, never by editing Git history. Production uses HTTPS, secure HttpOnly session cookies, SameSite=Lax, CSRF tokens on writes, and a database-backed eight-hour session. Trust proxy headers only from the configured hosting ingress.

Application logs go to stdout with request IDs and safe operational messages. Do not log request bodies, customer contact details, passwords, session tokens, provider credentials, or full webhook bodies. For an API error, use `X-Request-ID` to correlate the client response and server log; integration attempts retain provider-safe status/error fields.

## Public form and user access

Public intake requires a CSRF token, a privacy acknowledgment, an allowlisted field set, a honeypot, a 64 KiB request cap, a rate limit, and an idempotency key. Do not publish the development version for real customer intake. The demo intentionally disables writes. Staff may view team leads but mutate assigned leads only; admins can assign/archive/export and manage integration retry. User creation and role changes are an owner/admin operational task, not an open registration flow.

## Demo data and reset

The public demo contains synthetic `example.test` contacts only. Run `create_demo_data` with `DEMO_MODE=true` and strong configured demo passwords on a dedicated demo database. The command is idempotent and never changes existing demo passwords or roles. `reset_demo_data --confirm-demo-reset` deletes only leads marked `demo_seeded`, including their related synthetic history and integration records, then seeds the examples again. It refuses production mode, non-demo databases, and calls without the explicit flag. The Render daily job runs at 00:00 Asia/Singapore (16:00 UTC).

Do not load real business records into the public demo. Synthetic records can be reset daily, so users should not enter personal data or rely on demo changes persisting.

## Retention and backups

Keep leads and audit events for the pilot's agreed business retention period; no automated customer-data deletion policy is configured in the MVP. Set the actual period with the business owner before handling real inquiries. Demo-only records are reset each day. Provider webhook receipts and email attempts remain part of execution history until their associated demo lead is reset or the business data-retention process is agreed.

On Render, use paid PostgreSQL point-in-time recovery plus periodic logical export. Download logical backups to an account-controlled, encrypted offsite location; limit access and delete old copies according to the agreed retention period. Keep restore copies out of Git and local OneDrive sync.

## Restore and rollback

Restore to a new database first. Pause the email worker before restoration; inspect pending/processing alert executions and reconcile provider state before restarting live delivery. Verify migrations, users/roles, lead/task counts, application login, one synthetic workflow, and worker heartbeat. Then update the database connection and resume scheduled work. If verification fails, leave the original database attached and discard only the temporary recovery target.

Rollback the web release to the last known-good image. Database changes should use expand/contract migrations so the previous release remains compatible. A code rollback does not reverse a migration or an external email; evaluate those separately and record the decision.
