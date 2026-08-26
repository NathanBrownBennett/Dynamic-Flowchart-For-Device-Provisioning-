# Host environment sheet — names only

Status: prepare-only. Do not paste secret values into this file or commit a
host export. Populate these names in the selected host's configuration UI only
after the founder approves the provider and staging service.

## Runtime names

- `HOST`
- `PORT`
- `FLASK_DEBUG`
- `DATABASE_PATH`
- `FRONTEND_DIST`
- `SERVE_FRONTEND_AT_ROOT`
- `MAX_CONTENT_LENGTH`

## Operator and access-control names

- `PROVISIONING_ADMIN_TOKEN`
- `PROVISIONING_OPERATOR_IDENTITY_PROVIDER`
- `PROVISIONING_INVITE_POLICY`
- `PROVISIONING_SECRET_STORE`

The last three names are approval/inventory labels, not application settings.
The current bearer token must remain a local/staging automation secret and
must not be exposed to browser code or a public deployment.

## Outbound and catalogue names

- `ENABLE_LIVE_SCRAPING`
- `RETAILER_SEARCH_TERMS`
- `RETAILER_RESULT_LIMIT`
- `RETAILER_OBSERVATION_TTL_HOURS`
- `RETAILER_REFRESH_INTERVAL_MINUTES`
- `RETAILER_REQUEST_DELAY_SECONDS`
- `IMAGE_PROXY_ALLOWED_HOSTS`
- `IMAGE_PROXY_MAX_BYTES`
- `RETAILER_ALLOWED_HOSTS`
- `SCRAPER_MAX_HTML_BYTES`
- `PUBLIC_RATE_LIMIT`
- `PUBLIC_RATE_WINDOW`
- `CATALOGUE_FEED_SOURCE`
- `CATALOGUE_FEED_SOURCE_URL`
- `CATALOGUE_REFRESH_SCHEDULE`

The staging host may enable the bounded retailer-observation collector. It uses
fixed HTTPS search pages, no redirects, byte and time limits, a small fixed
query list, and a scheduled cache refresh. These observations are not described
as authorised retailer feeds and must be shown with a verify-before-purchase
warning. Credentialled provider adapters remain disabled until separately
approved.

## Host controls to record separately

- `HOSTING_PROVIDER_ACCOUNT`
- `HOSTING_SERVICE_NAME`
- `HOSTING_PERSISTENT_VOLUME`
- `HOSTING_SECRET_MANAGER`
- `HOSTING_ACCESS_LOG_POLICY`
- `HOSTING_BACKUP_POLICY`
- `HOSTING_ALERT_POLICY`

These are names-only approval records. No host, account, volume, secret,
backup or alert resource has been created by this work.
