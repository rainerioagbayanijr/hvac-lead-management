# Milestone 4 — follow-up tasks

Staff can add a dated next step to an assigned lead, then reschedule, complete, or cancel it. The team Follow-ups page shows pending, completed, and cancelled work and can filter pending tasks to overdue or due today. Overdue status is computed from the pending task's due time and the server clock; it is not a separate status that needs a scheduled job.

Due dates are collected and displayed in Singapore time, then stored as timezone-aware timestamps by Django/PostgreSQL. API writes use the lead's version and an action key, so retries do not create duplicate task events and stale updates return a conflict. Tasks follow lead ownership automatically. Marking a lead Won or Lost cancels its pending tasks in the same transaction; the lead history records how many were cancelled. Reopening does not restore old tasks.

## Screens and behavior

- Lead detail shows the task history, overdue status, scheduling form, and pending-task controls. The stage section warns that closing the lead cancels open follow-ups.
- Follow-ups navigation opens a paginated team list. Staff can complete, cancel, and reschedule pending tasks from the list. Filters separate open/completed/cancelled tasks and expose overdue/today views for open work.
- Customers are not contacted by the task system. Calls, messages, and reminders remain manual; no email or push reminders are sent.

## Verification

- Backend: 98 Django tests pass against PostgreSQL, including scheduling, timezone validation, authorization, idempotent retries, rescheduling, completion, overdue filtering, ownership after reassignment, and Won/Lost cancellation.
- Django system check passes; the new `0004_follow_up_task` migration applies locally and `makemigrations --check --dry-run` reports no model drift.
- Ruff lint and formatting checks pass; `git diff --check` is clean.
- Frontend formatting, TypeScript type-check, and production build pass using a clean temporary copy of the committed lockfile. The project's existing native module file was locked on Windows, so verification used a temporary dependency folder that was removed afterward.
- No dedicated automated browser test is added in this milestone; critical browser workflows remain in Milestone 7.

## Manual walkthrough

1. Open a lead owned by the current staff member (or log in as admin).
2. Schedule a task for a future Singapore date/time; confirm the task appears in both the lead detail and Follow-ups list.
3. Reschedule, complete, and cancel separate tasks; check their status filters and the activity history.
4. Schedule another task, then mark the lead Won or Lost; confirm the warning, cancellation, and activity summary.
5. Use a due time in the past through synthetic test data to check the overdue filter and label.

## Next milestone

Milestone 5 adds lead search and filters, a simple pipeline view, and carefully defined owner/response/follow-up metrics. Hosted demo and production deployment remain later milestones.
