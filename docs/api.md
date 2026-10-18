# API contract — Milestone 3

All application routes below use the prefix `/api/v1/`. Responses are JSON. Protected endpoints use Django sessions; application roles do not grant anonymous access.

| Method | Route | Access | Purpose |
| --- | --- | --- | --- |
| GET | `auth/csrf/` | Public | Return a masked CSRF token and set its cookie |
| GET | `auth/session/` | Public | Return authenticated state and safe current-user fields |
| POST | `auth/login/` | Public, explicit CSRF | Username/password to a rotated Django session |
| POST | `auth/logout/` | Authenticated, explicit CSRF | Invalidate the session |
| POST | `inquiries/` | Public, explicit CSRF/rate limit | Store/replay one service inquiry |
| GET | `leads/` | Authenticated | Paginated team lead summaries |
| POST | `leads/` | Authenticated staff/admin | Add a manually received inquiry |
| GET | `leads/{uuid}/` | Authenticated | Contact/service details and creation history |
| POST | `leads/{uuid}/claim/` | Authenticated staff/admin | Claim an unassigned active lead for self |
| POST | `leads/{uuid}/assignment/` | Admin role | Assign, reassign, or unassign a lead |
| POST | `leads/{uuid}/contact/` | Lead owner or admin | Record customer contact and first response |
| POST | `leads/{uuid}/stage/` | Lead owner or admin | Add a quote, change stage, or close Lost |
| POST | `leads/{uuid}/reopen/` | Admin role | Reopen a Won/Lost lead |
| POST | `leads/{uuid}/notes/` | Lead owner or admin | Append an internal note |
| GET | `team/` | Admin role | List active users for assignment |
| GET/HEAD | `health/` | Public | Minimal database-aware readiness |

The readiness alias `/health/` exists outside the prefix for hosting. Its response is `200 {"status":"ok"}` or `503 {"status":"unavailable"}`, with no database details.

## Public inquiry fields

Required: `submission_key` (UUID), `name` (maximum 120 characters), `service_type` (maintenance/installation/repair), and `privacy_acknowledged: true`.

Provide at least one of `phone` (maximum 40) or `email`. Optional `location` (250) and `requirements` (4,000) default to empty strings. Honeypot `company_website` must be empty. Unknown fields, including stage, owner, role, and source, are rejected.

The server chooses New stage, website source, no owner, and the receipt time. Contact fields are normalized. Lead and initial activity event are committed together.

- First accepted request: 201 and `{"reference":"lead-uuid"}`.
- Same key and normalized payload: 200 with the original reference and no new side effect.
- Same key and changed payload: 409 `submission_conflict`.
- A shared contact method with a different key is allowed; this may be another service request.

No public reference lookup exists. Public responses do not expose stored contact details.

## Sessions and CSRF

Get a token from `auth/csrf/` and send `X-CSRFToken` on writes. Use same-origin credentials. Login rotates the session and CSRF secret; the frontend refreshes its token before each write. Logout deletes the session. Ordinary requests do not extend the eight-hour expiry.

Invalid and inactive credentials use the same generic response. SessionAuthentication returns 403 for anonymous protected requests, distinguished by the `not_authenticated` code.

## Read responses

Lists return `count`, `next`, `previous`, and `results`, with 25 records per page and stable descending receipt-time/UUID ordering. Use `?page=2`. Search/filter controls and configurable page size are later work.

Summaries include ID, customer name, contact methods, service/stage labels, owner name and ID, source, and receipt time. Details additionally include location, requirements, first-contact/quote/closure fields, version, and readable activity summaries. Submission/action keys, fingerprints, and normalized-phone internals are never returned.

## Lead action requests

Every action POST includes `action_key` (a client-generated UUID) and `expected_version` (the version last read). The server locks the lead row, checks ownership and version, commits the change with its activity event, and increments the version. Retrying the same action key with the same actor and fields replays the saved result. Reusing the key with different fields returns `409 conflict`; an outdated version also returns `409 conflict`. Direct PATCH/DELETE on a lead remains unavailable.

- `claim/`: only an unassigned, open lead can be claimed.
- `assignment/`: `owner_id` is an active user ID or null. Only the admin application role can call it.
- `contact/`: `method` is phone/email/whatsapp/other; `summary` is optional. First contact time is kept once. Contacting a New lead moves it to Contacted.
- `stage/`: New can be marked Contacted or Lost; Contacted can be Quoted or Lost; Quoted can be Won or Lost. Quoted requires a positive `quote_amount` in SGD; Lost requires `loss_reason`. Won requires an existing quote.
- `reopen/`: an admin chooses New, Contacted, or Quoted. Quoted is available only if a quote exists. Historical close events remain in activity.
- `notes/`: `body` is a nonblank internal note up to 2,000 characters. Notes append to history and cannot be edited or deleted.
- Manual `POST leads/`: name, at least one contact method, service type, source, and (when supplied) a time-zone-aware `received_at` are validated. The server uses its current time when `received_at` is omitted. A staff creator owns the new lead; an admin creator leaves it unassigned. Receipt times in the future are rejected.

Staff can see all team leads but can mutate only assigned leads; they can self-claim unassigned active leads. Admin application roles can mutate and assign any lead. These checks are enforced by the API and services even if the interface is bypassed.

## Error format

`code`, `message`, optional `fields`, and a server-generated `request_id` form the standard DRF envelope. Django CSRF failures also return that JSON shape. `X-Request-ID` provides the matching reference.

| Status | Examples |
| --- | --- |
| 400 | validation_error, invalid_request |
| 403 | not_authenticated, invalid_credentials, permission_denied, csrf_failed |
| 404 | not_found for unavailable records under valid DRF routes |
| 405 | method_not_allowed |
| 409 | submission_conflict, conflict |
| 413 | payload_too_large |
| 429 | rate_limited, with Retry-After |
| 500 | internal_error, with no exception details |

Unresolved Django routes may still use Django's non-JSON 404 response. The client handles unreadable responses safely. APIs use no-store on normal responses; secrets and customer request bodies are not logged.

## Abuse controls

API body limit: 64 KiB. Inquiry attempts: 10 per fixed UTC hour/IP. Login attempts: 10 per fixed 15-minute window/account and 30 per window/IP. PostgreSQL locks serialize shared counters; subjects are hashed. Forwarded IP headers are ignored unless the immediate proxy is explicitly trusted. Counter pruning joins scheduled maintenance in the background-work milestone.
