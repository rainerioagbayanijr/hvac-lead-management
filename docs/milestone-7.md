# Milestone 7 — verification and hosted-demo readiness

The repository has a Docker multi-stage build that compiles the Vite app and serves it with Django on one origin. WhiteNoise serves versioned static assets. The Render Blueprint describes the demo web service, private managed PostgreSQL, one-minute fake email worker, Singapore-midnight synthetic-data reset, migrations, and first-deploy demo seed. HTTPS is provided at the hosting edge; Django uses secure session/CSRF cookies and trusts only the platform hostname.

The public demo profile is synthetic and read-only for customer intake. It seeds three demo roles, six fictional leads, task examples, simulated delivered alerts, and one safe retry example. `DEMO_MODE=true` forces the fake adapter on both the web and worker. The daily reset deletes only leads marked `demo_seeded`, then reseeds. It requires both demo mode and the explicit reset flag; account passwords and roles are not overwritten for existing users.

CI runs Django/PostgreSQL checks, Ruff, Prettier, TypeScript, Vite production build, and four Playwright workflows against a temporary PostgreSQL database. A local browser run also verifies public intake and authenticated workflow. No live-provider message is part of CI.

## Remaining account-owned operations

No public hosting account or Resend credentials were available to this workspace. Therefore the Blueprint has not been provisioned, the hosted demo URL does not exist, live provider acceptance/delivery has not been proven, and no hosted backup restore has been rehearsed. After provisioning: set strong demo credentials in provider secrets, run a restore to a separate database, verify the result, then perform a staged demo deploy. Keep production customer data in a different database and environment with `DEMO_MODE=false` and a reviewed Resend sender configuration.

See [deployment steps and rollback](deployment.md) for the release checklist.
