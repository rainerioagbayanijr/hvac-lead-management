# Product and permission contract

The app serves one air-conditioning company. Website inquiries enter automatically; staff manually enter phone, email, WhatsApp, and referral inquiries. Customer contact and quote preparation remain outside the app.

MVP stages: New, Contacted, Quoted, Won, Lost. Every open lead should have an owner and next action. The dashboard separates current pipeline totals from date-cohort response metrics.

## Target MVP permission policy

| Action | Customer | Staff | Admin |
| --- | --- | --- | --- |
| Submit inquiry | Yes | Yes | Yes |
| View active leads/history | No | All | All |
| Claim unassigned lead | No | Self only | Any active user |
| Reassign owned lead | No | No | Yes |
| Edit/contact/change stage/add notes/manage tasks | No | Assigned leads | All |
| Reopen/archive/restore | No | No | Yes |
| Export records | No | No | Yes |
| Business dashboard and full integration history | No | No | Yes |
| Manage integration settings/retry | No | No | Yes |
| Permanently purge | No | No | Controlled maintenance only |

Application role `staff` is separate from Django `is_staff`, which controls access to Django admin. An application admin role does not automatically grant technical admin/superuser privileges.

Milestones 1–2 implement users, explicit CSRF-protected login/logout, public intake, and authenticated lead list/detail. Staff and admin can view all existing leads. No lead mutation endpoints are exposed yet; object mutation permissions and workflow actions arrive in Milestone 3. The Lead admin stays read-only so it cannot bypass forthcoming services.

No SaaS tenancy, billing, uploads, technician dispatch, AI scoring, campaigns, or mobile app is included.
