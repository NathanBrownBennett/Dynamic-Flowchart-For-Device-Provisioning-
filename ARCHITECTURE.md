# Device Provisioning Toolkit architecture

## Current implementation

The application is a Flask 3 web app served by `wsgi.py` through Gunicorn in
the hosting image. `app.py` owns the HTTP routes, scoring/rule engine, SQLite
queries, Graphviz flowchart generation, response headers and operator gates.
`device_scraper.py` contains CSV loading plus optional Amazon/Currys HTTP
adapters. `create_db.py` is the original local database builder; the app now
also creates the minimum pilot schema at startup when the configured database
file is absent.

The normal read flow is:

```text
browser -> Flask route -> SQLite catalogue -> rule/scoring engine -> Jinja template
                                      \-> Graphviz SVG for device detail pages
```

The React/Vite migration uses this boundary:

```text
browser -> /app/ React bundle -> /api/v1/* Flask contract -> existing rule engine/SQLite
                              \-> Flask-only operator routes, proxy, refresh jobs and health
```

## Versioned API contract

The frontend only relies on these read-oriented endpoints:

- `GET /api/v1/healthz` → `{status, service, api_version}`.
- `GET /api/v1/catalogue/status` → product count plus source/freshness summaries.
- `GET /api/v1/devices` → `{items, page, page_size, total, live_scraping}`.
- `POST /api/v1/search` → the same collection envelope; filters are bounded and
  validated server-side.
- `GET /api/v1/devices/{id}` → `{item, api_version}` or a JSON 404.
- `GET /api/v1/devices/{id}/comparisons` → `{items, total, api_version}`.
- `POST /admin/catalogue/import` → protected operator-only feed ingestion;
  validates and atomically replaces the pilot catalogue.

Device items retain the existing rule-engine shape, including security score,
recommendations, operating-system inference and retailer links. The public
contract does not expose operator tokens or mutation endpoints.
Each item also exposes `catalogue.source`, `catalogue.retrieved_at`,
`catalogue.price_checked_at` and `catalogue.availability`, so the UI can
distinguish reviewed catalogue data from future live provider data.

Live retailer requests are a separate, disabled-by-default path. If explicitly
enabled, bounded retailer requests populate in-process caches and are never a
replacement for a reviewed production provider integration.

## Route boundary

| Route group | Purpose | Hosting status |
| --- | --- | --- |
| `GET /`, `/device/<id>`, `/resources`, `/flowchart/*` | Read-only catalogue, guidance and generated/static assets | Suitable for an invite-only pilot after normal web QA |
| `GET /healthz` | Liveness probe | Publicly safe; returns no catalogue or secret data |
| `POST /compare-devices`, `/generate-hardening-script` | Stateless user operations | Rate-limited in-process; add proxy/API limits in hosting |
| `POST /search-live`, `/get-current-price` | Optional provider access | Disabled unless `ENABLE_LIVE_SCRAPING=true`; terms and rate-limit review required |
| `POST /refresh-devices`, `/async-refresh`, `/validate-links` | Catalogue refresh/validation | Bearer operator gate; keep private until session auth, CSRF, audit logging and role checks exist |
| `GET /api/image-proxy` | Image compatibility proxy | HTTPS exact-host allowlist, public-DNS check, no redirects, content-type and 5 MiB limit |

## Configuration and data

All operational values come from environment variable names documented in
`.env.example`; no credential values belong in source control. SQLite is
single-instance pilot storage and the in-process caches are per-worker. A
production boundary needs a managed database, shared cache, background worker,
provider egress policy, structured logs, metrics, alerting, backups and a
recovery test.

## Public showcase boundary

`showcase/index.html` is static and contains no Flask or provider behavior. It
can be deployed as the public BStudioB showcase at
`https://provisioning.bstudiob.co.uk/` once the founder approves hosting and
DNS. The interactive Flask service should be routed separately and controlled;
this repository does not create that DNS record or hosting service.

## Licence

The repository uses the included **Custom Personal License**. It grants the
repository owner exclusive use/copy/modify/distribute permission, is
non-transferable and may not be sublicensed or redistributed without written
consent. This is an IP/licensing blocker for any third-party or public
redistribution until the owner confirms the intended BStudioB arrangement.
