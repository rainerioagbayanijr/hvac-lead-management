# ServiceDesk Leads — portfolio case study draft

## Problem

A small air-conditioning contractor receives repair, maintenance, and installation inquiries through a public form and manual channels such as phone, WhatsApp, email, and referrals. When an office team has no shared ownership queue, a new request can sit without an owner or promised next step.

## Product response

ServiceDesk Leads provides a team lead list, explicit owner assignment, a New → Contacted → Quoted → Won/Lost workflow, internal notes/history, dated follow-up tasks, overdue filtering, and a dashboard. An accepted website inquiry creates one durable internal email execution; attempts and provider delivery events are recorded so an admin can understand and safely retry eligible failures.

## Demonstrated engineering

- Python/Django/DRF owns permissions, validation, transactions, row locks, and metric definitions.
- PostgreSQL stores leads, append-only activity, follow-ups, idempotency keys, email attempts, provider receipts, sessions, and rate counters.
- React/TypeScript/Vite delivers a responsive same-origin interface; production static assets are served by Django/WhiteNoise.
- CI checks PostgreSQL behavior, Python lint/format, strict TypeScript/build, and four browser workflows.
- Fake email and synthetic `example.test` data make the demo repeatable without sending mail or exposing personal data.

## Evidence and limits

The checked-in automated tests and synthetic browser scenarios show expected behavior for the fixtures they cover. The synthetic dataset can demonstrate metrics and workflow transitions, but it does not establish that a real HVAC company will respond faster, lose fewer leads, or close more work. The public host, real provider delivery, and hosted restore rehearsal are not yet configured.

## Pilot measurement plan

For a real pilot, obtain business approval and define access/retention first. Record a four-week baseline from existing logs or a consistent manual sample, then collect the same fields in the app for a comparable period: received time, first human contact time, pending overdue follow-ups, assignment delay, and final stage. Compare medians and rates with cohort size, channel, and season noted. Do not claim causation from a small before/after sample. Keep quoted value separate from booked revenue and report only approved, aggregated results.

## Measurable now versus evidence required

Synthetic demo data can verify counts, status transitions, median response-time arithmetic, CSV behavior, and the retry record changing from failed to pending/delivered under the fake adapter. Customer response improvement, missed appointment reduction, conversion, revenue, and willingness to pay require a real business pilot and consented operational evidence.
