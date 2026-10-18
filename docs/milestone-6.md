# Milestone 6 — reliable email alert integration

Each accepted public inquiry writes one lead, its activity event, and one email execution in the same PostgreSQL transaction. An identical submission-key retry replays the original lead and does not add another execution. The alert includes a reference and service type, not the customer's contact details.

`integrations/` owns the deterministic fake and Resend adapters, the execution/attempt/webhook records, provider signature checks, and retry rules. A scheduled Django management command claims due work with short PostgreSQL row locks, records expiring leases, applies an eight-second HTTP timeout, and retries temporary failures up to five attempts at 1, 5, 15, and 60 minute intervals. Resend idempotency uses a stable execution key; automatic retry stops at 23 hours to leave margin inside the provider's 24-hour idempotency period. Uncertain delivery, expired windows, and exhausted attempts become Needs review.

Resend webhook signatures are checked against the raw body and signing secret. A unique provider event ID makes replay safe. Early and out-of-order events are retained and reconciled against provider message IDs. Permanent bounce/complaint events are not automatically retried. Admins can inspect execution history and request a safe retry; staff cannot change integration settings.

Demo mode forces the fake adapter on the server and blocks public inquiry writes. The frontend's displayed adapter is not trusted for that guarantee. Real delivery remains unverified until a provider test account, API key, verified sender domain, and webhook signing secret are configured. Resend approval is generally not needed for a test send, but the sender identity/domain must satisfy the account's current verification rules. The provider's free tier and any rate limits may change; check its official [price page](https://resend.com/pricing?product=marketing) before enabling real mail.

## Verification

Backend tests cover timeout/retry, permanent failure, attempt limits, lease recovery, safe-window expiry, signed/invalid/duplicate webhook events, early receipts, ordering, and admin/staff permissions. Browser tests exercise the visible admin retry. Fake mode is the always-available portfolio fallback and never sends external messages.
