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
- Missing expiries are bounded to the configured TTL; malformed, timezone-free,
  reversed or excessively long freshness windows are rejected.
- Failed provider runs do not fabricate replacement data.
- Last-known records are hidden from current ranking after expiry.
- `provider_runs` records status, count and a bounded error summary without
  storing credentials or response payloads.

## Retailer observation mode

`ENABLE_LIVE_SCRAPING=true` enables a bounded staging collector for fixed
Amazon UK and John Lewis search pages. It runs once when an empty database
starts and then on the configured background interval. The public search and
price routes read the cached database and never trigger an outbound request.

The collector accepts no user-supplied URL, follows no redirects, enforces
timeouts and a response-size ceiling, limits search terms and results, stores
no retailer images, and preserves the previous catalogue when a run fails.
It also preserves the previous catalogue when a refresh returns less than the
configured `RETAILER_MIN_REFRESH_RATIO`, preventing a partial retailer response
from replacing a fuller last-known catalogue.
Every record is labelled `observed`, low confidence and unofficial, with a
verify-before-purchase warning. Currys is not collected because its pages reject
the bounded request; no bypass is attempted.

This makes the staging catalogue useful without inventing prices, but it is not
a retailer-authorised product feed. Credentialled provider activation remains
disabled until terms, rate limits, attribution and credentials are approved.

## Production boundary

SQLite is suitable for a single-instance pilot only. Before multi-worker or
commercial traffic, migrate catalogue and run metadata to managed PostgreSQL,
use a shared cache, run provider jobs in a dedicated worker, add retry/dead
letter handling, structured logs, metrics, alerting, backups and a tested
restore. Keep the Flask/Gunicorn API and React static assets as the initial
serving boundary; a split frontend host is a later optimization, not a data
or security boundary.
