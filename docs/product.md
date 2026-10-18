# Product and permission contract

The app serves one air-conditioning company. Website inquiries enter automatically; staff manually enter phone, email, WhatsApp, and referral inquiries. Customer contact and quote preparation remain outside the app.

MVP stages: New, Contacted, Quoted, Won, Lost. Every open lead should have an owner and next action. The dashboard separates current pipeline totals from date-cohort response metrics.

## Target MVP permission policy

| Action | Customer | Staff | Admin |
| --- | --- | --- | --- |
| Submit inquiry | Yes | Yes | Yes |
| View active leads/history | No | All | All |
| Claim unassigned lead | No | Self only | Self only |
| Reassign owned lead | No | No | Yes |
| Edit/contact/change stage/add notes/manage tasks | No | Assigned leads | All |
| Reopen/archive/restore | No | No | Yes |
| Export records | No | No | Yes |
| Business dashboard and full integration history | No | No | Yes |
| Manage integration settings/retry | No | No | Yes |
| Permanently purge | No | No | Controlled maintenance only |

Application role `staff` is separate from Django `is_staff`, which controls access to Django admin. An application admin role does not automatically grant technical admin/superuser privileges.

Milestones 1–3 implement users, explicit CSRF-protected login/logout, public intake, team-wide lead viewing, claims/assignments, manual intake, contact/quote/stage changes, notes, and history. Staff see all leads, claim unassigned active leads, and update leads assigned to them. Admin application roles can assign/reassign and reopen leads. The Lead admin remains read-only so it cannot bypass workflow services.

No SaaS tenancy, billing, uploads, technician dispatch, AI scoring, campaigns, or mobile app is included.
