# Deployment and operations plan

## Recommended: one managed web service plus managed PostgreSQL

Use the included Render Blueprint in `deploy/render.yaml` for the public synthetic demo. It builds the React app and Django API into one container and serves both at one HTTPS origin. PostgreSQL is private to the same Singapore region. A one-minute cron runs the database-backed email worker, and a second cron resets only demo-seeded records at 00:00 Singapore time. The web service's first-deploy hook adds synthetic accounts and sample data after migrations.

This is the smallest operational step up from local development: managed TLS, deploy history/rollback, cron support, PostgreSQL, and point-in-time recovery without a Redis service or a separately hosted browser app. Render supports Docker web services, auto HTTPS, cron schedules in UTC, and managed PostgreSQL. Paid database backups include PITR (three days on Hobby workspace, seven days on Pro) and dashboard logical exports retained seven days. Verify workspace and compute prices before provisioning; provider pricing changes.

Current rough demo estimate (USD, before tax and usage): approximately **$15–$17/month** with a $7/month starter web service, the $6/month 0.1 CPU/256 MB PostgreSQL plan plus storage at $0.30/GB-month, and two cron jobs at a $1/month minimum each. Outbound bandwidth above the included allowance, domains, email volume, and a higher workspace plan can add cost. This estimate uses [Render's current pricing](https://render.com/pricing), [compute plan definitions](https://render.com/docs/compute-plans), [cron billing](https://render.com/docs/cronjobs), and [database recovery guide](https://render.com/docs/postgresql-backups), checked 18 October 2026. The small database plan is for a portfolio demo; start a real business deployment on a separately budgeted database plan.

The template's `DEMO_MODE=true` deliberately disables public inquiry writes and forces fake email. For a business environment, create a separate Render environment with its own database and secrets, set `DEMO_MODE=false`, add a verified Resend sender and webhook signing secret, then exercise the private provider test. Never switch the public synthetic demo to live sending.

## Three practical approaches

| Approach | Complexity and likely costs | Jobs, HTTPS, backup, maintenance |
| --- | --- | --- |
| Managed app hosting + managed PostgreSQL (recommended) | Lowest setup burden; estimate above for Render. Includes separate web, database/storage, cron compute, and overage categories. | Built-in scheduled jobs; automatic HTTPS; paid PostgreSQL PITR/logical exports. Provider handles OS/database operations; you still manage secrets, schema migrations, application logs, and restore rehearsal. |
| One VPS | Lowest infrastructure bill, but you operate Linux, reverse proxy, container/app processes, firewall, PostgreSQL, and backups. As a price reference, Hetzner's official 15 June 2026 list shows a small CAX11 at $6.99/month in Germany/Finland, excluding IPv4; region choice affects latency. Budget extra for IP, snapshot/object backup, and domain. | Use systemd timer or cron; configure Let's Encrypt and renewals; schedule encrypted off-site `pg_dump` and test restores. You own patching, PostgreSQL upgrades, firewall, monitoring, and recovery. |
| Separate frontend and backend hosting | React static hosting plus a Django web service and managed PostgreSQL. Vercel Pro is currently $20/month with $20 usage credit; add backend, database, job, and overage costs. Separate origins require credentialed CORS, CSRF trusted origins, and careful cookie/site configuration; a custom subdomain arrangement is preferable. | Static frontend has HTTPS/CDN; backend still needs its own job runner and TLS; DB backup depends on provider. More deploys and cross-origin debugging for little MVP benefit. |

VPS price reference: [Hetzner's official June 2026 price adjustment](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/), checked 18 October 2026. Separate frontend reference: [Vercel Pro pricing](https://vercel.com/pricing), checked 18 October 2026. These are provider list prices, not a tax-inclusive quote; VPS storage/backup and frontend usage are additional.

## Environments

- **Local:** Django development settings load root `.env`; PostgreSQL runs in the named Docker Compose service; Vite proxies `/api` to Django. Use synthetic records only. `INTEGRATION_ADAPTER=fake` is the default.
- **CI:** a throwaway PostgreSQL 17 service, fake adapter, random test data, and isolated Playwright browser. CI secrets are test-only constants.
- **Public demo:** dedicated database, `DEMO_MODE=true`, fake adapter enforced server-side, synthetic accounts/leads only, public intake disabled, guarded daily reset. Use a strong shared demo password configured as provider secrets; communicate it on the portfolio page after deployment.
- **Business production:** separate account environment and database, `DEMO_MODE=false`, strong secret key, explicit allowed origin/host, verified Resend sender, and private provider secrets. Real customer records never enter demo or CI.

## Deployment checklist

1. Create the hosting workspace and review the live estimate, region, budget alerts, and paid database recovery window.
2. Connect the repository and apply `deploy/render.yaml`; provide unique admin/staff demo passwords when prompted. Review Blueprint changes before applying them.
3. Confirm the database is private and colocated with the web/cron jobs; verify environment variables contain no demo/production secret crossover.
4. Confirm migrations and the initial seed complete, `/health/` returns 200, the root page loads, and SPA routes such as `/app/leads` return the application shell.
5. Sign in as demo admin and staff; verify intake is visibly disabled, fake mail is shown, assignment permissions hold, and retry changes only the recorded simulation.
6. Wait for worker freshness; inspect cron logs and verify the seeded retry remains available until used or reset.
7. Trigger one reset manually in the demo environment and confirm only `demo_seeded` leads are replaced and users/passwords remain unchanged.
8. Create and restore a database export into a different, temporary database. Verify counts and sign-in before removing that temporary copy.
9. Only after all checks pass, link the public URL and current synthetic screenshots in the portfolio.

## Backups, restore, and rollback

Use paid Postgres point-in-time recovery for recent accidental changes and create periodic logical exports for portable recovery. Keep copies in an account-controlled offsite location with access limited to the owner; the repository does not store customer exports. A recovery target must be a separate database: do not overwrite production during rehearsal.

For a restore, pause email and reset cron jobs first so no new external side effects occur. Restore PITR or import the logical export into a new database; verify schema migrations, lead/task counts, user roles, session behavior, and the integration execution queue. Treat pending/processing executions as uncertain: reconcile their provider status before resuming a live worker. Point the web service to the recovered database only after the checks pass, then resume the worker and monitor its heartbeat.

For an application rollback, use the last known-good image/deploy. Keep migrations backward-compatible across one release: add nullable/new columns first, deploy code that can use them, and remove old columns only in a later release. If the failed release changed schema, restore application and database to a compatible pair. Do not replay external email solely because a database restore revived pending rows; use provider idempotency and execution history to reconcile first.

## What is configured versus completed

The repository has the Docker build and Render Blueprint; no hosting account was connected, so no cloud service has been created and there is no public URL. Live email credentials were not provided, and provider delivery has not been claimed as verified. Restore and rollback procedures are documented but the hosted rehearsal is pending the provider account.
