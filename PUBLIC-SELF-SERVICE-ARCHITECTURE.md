# Public self-service architecture

This document describes the intended hosted boundary for the Device Provisioning
Toolkit. It is an architecture target, not a production-readiness claim.

## Boundary

- The browser-facing frontend will consume a versioned, read-only API for
  catalogue search, recommendations and security guidance.
- Provider access (retailer APIs or permitted feeds) will run in isolated worker
  processes. Browser requests must never trigger arbitrary outbound fetches.
- Provider adapters will write normalised results to a bounded cache with a
  source, retrieval timestamp, expiry timestamp and attribution link.
- Every public product result will expose freshness and availability caveats;
  the service will not describe a stale catalogue price as a live guarantee.
- A stale-but-reviewed cache may be served when a provider is unavailable;
  uncached provider failures return a safe, explainable error.
- The current Flask/SQLite implementation is a single-instance pilot shape.
  SQLite and the in-process cache are not a production multi-instance store.

## Public API target

The eventual API should expose only the minimum public operations:

- `GET /api/v1/healthz` — liveness/readiness without secrets or catalogue data.
- `GET /api/v1/criteria` — bounded choices for the guided workflow.
- `GET /api/v1/sources/{source}/status` — coarse source freshness only.
- `GET /api/v1/devices` — bounded, paginated catalogue results.
- `GET /api/v1/devices/{id}` — one reviewed device record for an explicit use case.
- `POST /api/v1/search` — validated query/filter input with rate limits.
- `GET /api/v1/sources/{source}/status` — coarse provider freshness only.

Operator refresh, link validation and any catalogue mutation remain private
operator operations. They must use authenticated sessions, CSRF protection,
audit logging and explicit role checks before they are enabled online.

## Caching and timestamps

Every provider-derived field must retain its source and retrieval time. Price
and availability are observations, not guarantees. The UI must show the
retrieval time and a “verify before purchase” notice. Cache keys must include
the provider, query/filter set and locale; cache entries must have a bounded
size and expiry.

## Abuse and failure controls

The hosting layer and API must enforce request/body limits, per-IP and per-user
rate limits, bounded provider timeouts, retry budgets, response-size limits and
outbound egress allowlists. Provider errors must not reveal stack traces,
credentials, internal URLs or raw retailer responses.

## Scoring and user-facing wording

Security scores are transparent heuristics based on the available device data
and selected use case. They are not certification, a guarantee of security,
procurement advice or a substitute for an organisation's own assessment.

## Account and data boundary

V1 can remain anonymous and stateless. If accounts are introduced, they are
only for saved comparisons/preferences and must have export and deletion paths.
Do not collect employee names, serial numbers, inventories or organisation
data in the public self-service flow without a separately approved privacy and
retention design.
