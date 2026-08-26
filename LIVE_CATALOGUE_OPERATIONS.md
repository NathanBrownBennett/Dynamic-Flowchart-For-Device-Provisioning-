# Live catalogue operations

## Local/staging import

Use an operator-authenticated `POST /admin/catalogue/import` with a reviewed
JSON feed. The importer validates canonical identity, HTTPS attribution URLs,
offer prices, dates, evidence types and bounded record counts, then replaces
the catalogue and its evidence tables in one SQLite transaction.

`ALLOW_SAMPLE_DATA=true` is for local deterministic tests only. The default is
false; when no approved feed is present, the public API reports `empty` or
`unavailable` and returns no sample products.

## Refresh policy

- Product catalogue default TTL: 168 hours.
- Offer default TTL: 48 hours.
- Provider responses must include a checked time and explicit expiry.
- Failed provider runs do not fabricate replacement data.
- Last-known records are hidden from current ranking after expiry.
- `provider_runs` records status, count and a bounded error summary without
  storing credentials or response payloads.

The legacy scraper module is retained only for local maintenance compatibility;
the public search, current-price, refresh and background paths do not call it.
Provider activation is disabled until terms, rate limits, attribution and
credential injection are approved.

## Production boundary

SQLite is suitable for a single-instance pilot only. Before multi-worker or
commercial traffic, migrate catalogue and run metadata to managed PostgreSQL,
use a shared cache, run provider jobs in a dedicated worker, add retry/dead
letter handling, structured logs, metrics, alerting, backups and a tested
restore. Keep the Flask/Gunicorn API and React static assets as the initial
serving boundary; a split frontend host is a later optimization, not a data
or security boundary.
