# Milestone 3 — ownership and sales workflow

## Delivered behavior

- Staff and admins can see the team lead list. Staff can claim an unassigned active lead and change only leads assigned to them. Admin application roles can assign, reassign, or unassign any lead.
- Staff can record phone, email, WhatsApp, or other customer contact. The first-contact timestamp is written once and is not inferred from a stage or note. Recording the first call moves a New lead to Contacted.
- A Contacted lead can receive a positive SGD quote and move to Quoted. A Quoted lead can become Won. Any open lead can become Lost when staff provide a reason. An admin can reopen a closed lead while the earlier closure remains in history.
- Staff can add append-only internal notes. Each saved workflow change and note writes its activity event in the same database transaction.
- Staff can manually enter an inquiry with its source and time received. A staff-created inquiry is assigned to its creator; an admin-created inquiry starts unassigned.
- Actions include an idempotency key and expected record version. A retry of the same action has one effect; changed data under a reused key or a stale edit returns a conflict.

## Milestone checklist

- [x] Staff claim unassigned leads; admins assign, reassign, and unassign.
- [x] Staff changes are limited to owned leads; all staff can still view the team list.
- [x] Record contact method and first-response time once.
- [x] Save quotes and enforce New → Contacted → Quoted → Won, with a reason for Lost.
- [x] Allow admin reopening while preserving the earlier closure event.
- [x] Save append-only notes and activity in the same transaction as each change.
- [x] Add manual inquiries with source tracking and time-zone validation.
- [x] Verify permissions, conflict/retry behavior, simultaneous claims, CSRF, and rollback.

Calls, customer messages, quotations, and appointments remain manual. No external alert is sent in this milestone.

## Verification

All **87 backend tests pass** against PostgreSQL, including staff visibility and ownership checks, staff claims, admin assignment and reopening, stale versions, simultaneous claims, note replay, CSRF, first-contact preservation, quote and loss requirements, closure history, manual source/time validation, unknown fields, and rollback when activity writing fails. The earlier Milestone 1–2 tests continue to pass.

Django system checks, migration-drift checks, Ruff lint/format, strict TypeScript checking, Vite production build, and Prettier checks pass. A browser walkthrough exercised inquiry intake, staff claim/contact/quote/note/Won, admin reopening and reassignment, and manual referral entry. The detail page had no horizontal overflow at either 390px or the normal desktop viewport. The walkthrough uses synthetic details and is captured in [`screenshots/milestone-3-workflow.png`](screenshots/milestone-3-workflow.png). The local database now contains these two synthetic walkthrough inquiries in addition to the earlier demo records.

## Next milestone

Milestone 4 adds follow-up tasks: create, reschedule, complete, and cancel reminders; show overdue tasks; transfer open tasks with lead reassignment; and handle tasks when a lead closes or reopens.
