# Controlled hosting runbook

## Current boundary

This repository contains a Flask application with a SQLite catalogue, Graphviz
flowchart generation, retailer HTTP requests and optional live scraping. The
WSGI/Procfile path is the primary non-Docker deployment shape; Docker remains
an optional packaging path. Neither path is a production readiness claim.

The safe first deployment is an invite-only pilot with `ENABLE_LIVE_SCRAPING=false`,
no public admin token, and a persistent single-instance volume for the demo
SQLite database. Use a BStudioB-owned host and keep the repository private until
the licence/IP and security review are complete.

The public presentation boundary should be a static showcase containing the
product explanation, screenshots and licence notice. The showcase wording
must identify the interactive service as an invite-only pilot: it provides no
public account creation, sign-up collection or operator controls. Keep the
Flask app behind a separate controlled path/service (for example
`/interactive`) with its own access policy. The included `showcase/index.html`
is a static starting point; DNS, routing and hosting changes remain
founder-gated.

The initial interactive migration is built with `frontend/` and served by
Flask at `/app/` when `frontend/dist` exists. The Dockerfile builds that bundle
in a Node stage and copies only the compiled assets into the Python runtime.
The later split-host option is to serve the same static bundle from a frontend
host and point it at a separately controlled Flask API origin; that split must
retain HTTPS, CORS allowlisting, API rate limits and the existing backend
security boundary.

## Local checks without Docker

```sh
python -m py_compile app.py device_scraper.py wsgi.py
python -c 'from app import app; print(app.test_client().get("/healthz").status_code)'
python -c 'from app import app; print(app.test_client().get("/api/v1/devices?page_size=1").status_code)'
PORT=8002 python app.py
```

## Optional container checks

```sh
docker build -t provisioning-toolkit:local .
docker run --rm -p 8002:8002 provisioning-toolkit:local
curl -fsS http://127.0.0.1:8002/healthz
```

The Docker daemon is only required for the optional container checks. A normal
Python WSGI host can use [HOSTING_NON_DOCKER.md](HOSTING_NON_DOCKER.md).

The prepared Railway invite-only staging route is documented in
[STAGING_RAILWAY_RUNBOOK.md](STAGING_RAILWAY_RUNBOOK.md). It uses one Gunicorn
worker because the pilot catalogue is SQLite-backed; do not scale it
horizontally or treat the route as a production deployment.

The founder has reported that the existing Railway workspace is now on its
Free plan. Treat that as a no-cost staging allowance only: verify the project
owner, service health, persistence and any sleep/credit limits before relying
on it. No payment, custom domain or production data should be added to this
route.

Railway currently blocks creation of another project because the Free-plan
resource-provisioning limit is exceeded. The device-provisioning service must
remain separate from Buildy; the prepared Render Free blueprint is the
no-cost fallback. Render login/account authorisation is required before that
blueprint can be created.

### No-cost Render staging alternative

`render.yaml` contains the Render Free Docker blueprint for a
constrained staging/demo service. Docker is used because the app needs both
Python and the Vite/Node build stage. It deliberately uses one worker,
disables live scraping, does not configure a custom domain, and places SQLite
on `/tmp` because Render Free has no persistent filesystem. Treat the service
as disposable and read-only: do not enable catalogue mutation, operator
controls, or personal data. The deployed staging service is
`https://bstudiob-device-provisioning-staging.onrender.com` (commit `1904ba5`,
Free plan, separate from Buildy). Render Free services sleep when idle, so
this is not an always-on or production substitute for a paid persistent host.

Live staging smoke checks on 20 August 2026 returned HTTP 200 for both
`/healthz` and `/`; `/healthz` returned the device-provisioning service status
and the root returned the React/Vite application shell. No custom domain,
secret, payment or production data was configured.

The browser prerequisites and current Chromium status are recorded in
[BROWSER_TESTING.md](BROWSER_TESTING.md). The prepared, unapplied host and
DNS sheets are [HOST_ENVIRONMENT_SHEET.md](HOST_ENVIRONMENT_SHEET.md) and
[DNS_TLS_CHANGE_SHEET.md](DNS_TLS_CHANGE_SHEET.md).

## Required environment

Copy `.env.example` into the hosting platform's secret/configuration UI. Do
not put secrets in the repository. Generate a long random
`PROVISIONING_ADMIN_TOKEN` only when an authenticated operator path has been
approved. Leave it unset in public/demo environments: refresh and validation
routes then return `503` by design.

The provider settings are intentionally split into two groups:

- Safe configuration: `SERPAPI_AMAZON_SEARCH_TERM`, `SERPAPI_RESULT_LIMIT`,
  `EBAY_SEARCH_TERM`, `EBAY_RESULT_LIMIT`, `OSV_PACKAGE_NAME`,
  `OSV_ECOSYSTEM` and `OSV_PACKAGE_VERSION`.
- Secret/approval-gated configuration: `SERPAPI_API_KEY`, `EBAY_CLIENT_ID`,
  `EBAY_CLIENT_SECRET` and any Amazon PA API credentials.

Do not enable `PROVIDER_SYNC_ENABLED` until the provider account, terms,
permitted fields, image use, retention period, refresh budget and attribution
have been approved. A provider job creates a review draft first; it does not
automatically replace the hosted catalogue.

## Before a hosted pilot

1. Confirm BStudioB ownership of the repository, deployment account and data.
2. Replace or review retailer scraping against each retailer's permitted API or
   terms; scraping remains disabled by default.
3. Use an approved persistent database/backup plan if catalogue edits are
   needed. SQLite is single-instance pilot storage, not a production database.
4. Put the service behind HTTPS, a reverse proxy, rate limiting and provider
   access logs. Add authentication/CSRF protection before enabling operator
   actions.
5. Keep `IMAGE_PROXY_ALLOWED_HOSTS` narrowly scoped and review image licences.
6. Run a security review covering mutation routes, SSRF, outbound requests,
   generated scripts, retailer links, privacy/retention and support processes.
7. Only after the above, create the founder-approved `provisioning.bstudiob.co.uk`
   DNS record and run an invite-only pilot.

## Known blockers

- Mutation routes have a bearer-token gate but no user/session authentication;
  they must not be exposed publicly.
- The image proxy is restricted to an allowlist and now applies HTTPS,
  public-DNS, content-type and 5 MiB response-size checks; hosting-level egress
  and rate limiting are still required.
- Live scraping is disabled by default and needs permitted data sources.
- SQLite is not suitable for concurrent production instances.
- No hosting resource, DNS record, payment flow or production credential has
  been created by this work.
