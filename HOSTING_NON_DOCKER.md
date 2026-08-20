# Non-Docker hosting path

Docker is optional. The application can run as a normal Python WSGI service:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-hosting.txt
python app.py
```

For a hosted process, use the included `Procfile` or the equivalent command:

```sh
gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 wsgi:app
```

The host must provide Python 3.10+, SQLite storage, and either the Graphviz
system binary or no Graphviz at all—the app now generates a readable SVG
fallback when Graphviz is unavailable. Use a persistent writable data path for
`DATABASE_PATH` during a pilot.

## Subdomain shape

The intended public service is a founder-approved subdomain such as
`provisioning.bstudiob.co.uk`. Set `SERVE_FRONTEND_AT_ROOT=true` so the React
application is served at `/`, while Flask continues to serve `/api/v1/*` and
the protected operator routes. DNS, TLS, hosting-account setup and reverse
proxy configuration remain external approval steps.

The public showcase remains separate from this interactive service. It should
not share operator endpoints, credentials or database access.

## Product data boundary

The first hosted version should use a reviewed catalogue plus permitted product
feeds or affiliate APIs. Browser requests must not scrape retailers directly.
Provider ingestion belongs in a bounded background job with source attribution,
retrieval timestamps, expiry, retries, and safe stale-cache behavior. Retailer
terms and commercial/affiliate arrangements must be approved before enabling
any live provider integration.

The first approved feed can be loaded through the protected
`POST /admin/catalogue/import` endpoint. It accepts a JSON object containing a
`source`, optional HTTPS `source_url`, optional `retrieved_at`, and 1–500
product records. The endpoint validates the records and replaces the pilot
catalogue atomically; it does not fetch the supplied URL. Keep the bearer token
private and use a real operator authentication layer before exposing this path
to a public network.

For a local or scheduled operator import, use the equivalent CLI without
network access:

```sh
python scripts/import_catalogue.py --feed catalogue-feed.example.json
```
