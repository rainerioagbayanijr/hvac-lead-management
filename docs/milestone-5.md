# Milestone 5 — working interface and dashboard

## Delivered

- Server-side case-insensitive search and validated stage, source, service, owner, archive, and overdue filters. The URL carries list filters and the paginated API uses stable ordering.
- A stage-grouped pipeline and a business dashboard linked to the work behind each metric.
- Current active pipeline counts, new leads in the latest 30 days, active leads waiting for first contact, pending overdue tasks, current Quoted-stage SGD value, median first-response time with sample coverage, and a mature 90-day win rate.
- Admin-only archive/restore and filtered CSV export capped at 10,000 rows. Cells beginning with spreadsheet formula characters are escaped.
- Archiving records an activity event and cancels pending follow-ups. Restoring a lead does not silently revive those cancelled tasks.

## Metric definitions

All time windows use the server's aware UTC instants; the interface displays Asia/Singapore time. The dashboard is generated at the returned `generated_at` time.

| Metric | Calculation |
| --- | --- |
| Pipeline | Count of nonarchived leads by their current stage, including Won and Lost |
| New leads, 30 days | Nonarchived leads with `received_at >= generated_at - 30 days` |
| Awaiting first contact | Active New or Contacted leads with no `first_contact_at` |
| Overdue follow-ups | Pending tasks with `due_at < generated_at`, regardless of lead archive status (archive cancels pending tasks) |
| Quoted value | Sum of quote amounts for active leads currently in Quoted; excludes Won/Lost and is not recognized revenue |
| Median response time | Median of `first_contact_at - received_at` for active leads received in the prior 30 days and first contacted by `generated_at`; includes responded count and eligible lead count |
| Win rate | Leads received from 120 days ago (inclusive) through 30 days ago (exclusive) whose current stage is Won, divided by all active leads in that received-date cohort; empty cohort yields null |

The win rate uses a 90-day mature intake cohort so newer opportunities have time to close. Reopened leads are classified by current stage. These are operational indicators, not audited financial results.

## Verification

- `backend/crm/tests/test_dashboard_queries.py` checks filter validation, role-safe owner filters, archived visibility, pagination ordering, and known metric fixtures.
- `backend/crm/tests/test_metrics_and_exports.py` covers archive/restore, task cancellation/history, admin permissions, export cap, and CSV formula safety.
- Frontend format, strict TypeScript, production build, and the four browser workflows are run in CI.
