# Railway staging runbook — BStudioB device provisioning toolkit

Status: prepared for the approved invite-only staging route; not deployed.

## Service shape

- Service: BStudioB-owned Railway staging service (never personal production).
- Runtime: Python/Gunicorn via `Procfile`.
- Workers: one process for the SQLite pilot; do not scale horizontally.
- Public hostname: do not generate or publish until DNS/TLS is approved.
- Health check: `GET /healthz`.
- Live scraping: disabled.
- Data: reviewed local sample catalogue on an approved persistent volume.

## Configuration names

Set these in Railway's variable/secret UI only; values are intentionally not
stored here:

```text
HOST=0.0.0.0
PORT=${{PORT}}
FLASK_DEBUG=false
DATABASE_PATH=/app/data/devices.db
SERVE_FRONTEND_AT_ROOT=true
ENABLE_LIVE_SCRAPING=false
PROVISIONING_ADMIN_TOKEN=<staging secret, never browser-exposed>
IMAGE_PROXY_ALLOWED_HOSTS=<reviewed hosts only>
RETAILER_ALLOWED_HOSTS=<reviewed hosts only>
PUBLIC_RATE_LIMIT=30
PUBLIC_RATE_WINDOW=60
```

Do not add production credentials, affiliate keys, personal data, or a
service-role/database secret. Keep mutation routes unavailable until a proper
authenticated operator layer is configured.

## Deployment and verification order

1. Confirm the Railway project is BStudioB-owned and staging-labelled.
2. Confirm the repository/branch and build command; do not deploy an
   unreviewed branch.
3. Add the variables above through Railway's secret manager.
4. Attach one persistent volume at `/app/data` only if the pilot requires
   catalogue edits; otherwise use the bundled reviewed feed.
5. Deploy without a custom/public domain.
6. Verify `/healthz`, `/api/v1/devices?page_size=1`, React root serving,
   security headers, rate limits, import validation and rollback behavior.
7. Run the installed Playwright suite against the staging URL.
8. Stop and record evidence. Request separate approval for DNS, custom domain
   and any public showcase link.

## Explicit stop conditions

- Any request for payment, plan upgrade or paid resource.
- Any request for a public domain or DNS/TLS change.
- Any need to enable live retailer scraping or affiliate tracking.
- Any need to expose operator mutation routes.
- Any attempt to scale beyond one SQLite-backed instance.
