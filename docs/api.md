# API contract — Milestone 2

All application routes below use the prefix `/api/v1/`. Responses are JSON. Protected endpoints use Django sessions; application roles do not grant anonymous access.

| Method | Route | Access | Purpose |
| --- | --- | --- | --- |
| GET | `auth/csrf/` | Public | Return a masked CSRF token and set its cookie |
| GET | `auth/session/` | Public | Return authenticated state and safe current-user fields |
| POST | `auth/login/` | Public, explicit CSRF | Username/password to a rotated Django session |
| POST | `auth/logout/` | Authenticated, explicit CSRF | Invalidate the session |
| POST | `inquiries/` | Public, explicit CSRF/rate limit | Store/replay one service inquiry |
| GET | `leads/` | Authenticated | Paginated team lead summaries |
| GET | `leads/{uuid}/` | Authenticated | Contact/service details and creation history |
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

Summaries include ID, customer name, contact methods, service/stage labels, owner display name, source, and receipt time. Details additionally include location, requirements, timestamps, version, and creation activity. Submission keys, fingerprints, and normalized-phone internals are never returned.

POST on the list and PATCH/DELETE on details are unavailable. Staff lead editing, assignments, and object mutation permissions belong to Milestone 3.

## Error format

`code`, `message`, optional `fields`, and a server-generated `request_id` form the standard DRF envelope. Django CSRF failures also return that JSON shape. `X-Request-ID` provides the matching reference.

| Status | Examples |
| --- | --- |
| 400 | validation_error, invalid_request |
| 403 | not_authenticated, invalid_credentials, permission_denied, csrf_failed |
| 404 | not_found for unavailable records under valid DRF routes |
| 405 | method_not_allowed |
| 409 | submission_conflict |
| 413 | payload_too_large |
| 429 | rate_limited, with Retry-After |
| 500 | internal_error, with no exception details |

Unresolved Django routes may still use Django's non-JSON 404 response. The client handles unreadable responses safely. APIs use no-store on normal responses; secrets and customer request bodies are not logged.

## Abuse controls

API body limit: 64 KiB. Inquiry attempts: 10 per fixed UTC hour/IP. Login attempts: 10 per fixed 15-minute window/account and 30 per window/IP. PostgreSQL locks serialize shared counters; subjects are hashed. Forwarded IP headers are ignored unless the immediate proxy is explicitly trusted. Counter pruning joins scheduled maintenance in the background-work milestone.
