# Milestone status and founder handoff

Date: 2026-08-19

## Completed locally

- The Flask application has a production WSGI entrypoint (`wsgi.py`), a safe
  `/healthz` endpoint, security headers, bounded request sizes and rate
  limiting.
- The application runs without Docker. Gunicorn, a virtual environment and
  the `Procfile` are the intended pilot path; Graphviz is optional because a
  readable SVG fallback is available.
- The React/Vite interactive frontend is served by Flask when
  `SERVE_FRONTEND_AT_ROOT=true`. Flask remains responsible for API routes,
  operator authentication, refresh operations, image proxying, persistence
  and health checks.
- The read-only API is versioned under `/api/v1`. The frontend shows plain
  English recommendations, security and performance considerations,
  benchmark-style comparisons, retailer links and catalogue freshness/source
  information.
- Catalogue imports are local-file/operator controlled, validated, bounded and
  atomic. Live retailer scraping remains disabled by default.
- Image proxying is restricted to HTTPS hosts on an explicit allowlist, with
  DNS checks, no redirects, timeouts, content-type checks and a 5 MiB limit.
- The static public showcase remains separate from the interactive application.
- SQLite limits, the future database/cache/worker/observability boundary and a
  no-PII self-service architecture are documented.
- Local staging/sample-feed acceptance, browser requirements, and names-only
  host/DNS preparation sheets are documented in
  `STAGING_SAMPLE_FEED_ACCEPTANCE.md`, `BROWSER_TESTING.md`,
  `HOST_ENVIRONMENT_SHEET.md` and `DNS_TLS_CHANGE_SHEET.md`.
- An approved Railway staging route is prepared locally in
  `STAGING_RAILWAY_RUNBOOK.md`. The SQLite pilot is constrained to one
  Gunicorn worker; no Railway service, project, volume or domain has been
  created.
- A no-cost Render Free staging blueprint is prepared in `render.yaml`. It is
  intentionally disposable (`/tmp` SQLite), read-only/demo-oriented and has
  no custom domain or secret values; no Render service has been created.
- Founder reports that the existing Railway workspace was downgraded to its
  Free plan. This preserves a no-cost staging option, but the plan, service
  health, persistence and public URL remain unverified from this worktree.
- Railway currently reports that the Free-plan resource-provisioning limit is
  exceeded, so a separate device-provisioning project cannot be created there
  without an upgrade. The existing Buildy project is intentionally not being
  reused.

## Verification completed

- Backend unit/security suite: 8 tests passed.
- Frontend API contract suite: 2 tests passed.
- Vite production build: passed.
- Python compilation for the application, WSGI entrypoint and catalogue CLI:
  passed.
- Catalogue import CLI smoke test with a temporary SQLite database: passed.
- Disposable staging restart-preservation and malformed-feed atomicity checks:
  passed.
- Invite-only static showcase wording check: passed.
- `git diff --check`: passed.
- Playwright Chromium end-to-end suite: 7 tests passed after the local
  Chromium prerequisite was installed.
- Railway staging configuration review: prepared locally; founder-reported
  Free-plan status is not a deployment or health verification.
- Docker and external browser deployment were not required for this milestone;
  the browser suite ran locally against the disposable staging server.

## Founder approval required before online setup

The implementation must stop here until the owner chooses and authorises the
following external decisions:

1. Confirm the BStudioB-owned Railway staging project/account and persistent
   volume arrangement; no personal Railway project is approved for production.
2. DNS and TLS creation for the chosen BStudioB subdomain, such as
   `provisioning.bstudiob.co.uk`.
3. An approved product catalogue source, including provider/affiliate terms,
   permitted fields, refresh frequency and attribution requirements.
4. The operator identity/authentication provider and secret-injection method.
   The current bearer token is suitable for local/staging control only.
5. The production data boundary: managed database, shared cache, background
   worker, backups, logs, metrics and alerting.
6. Confirmation of the intended licence/IP arrangement for public or
   third-party hosting.

No DNS, hosting account, provider integration, credential, payment, legal
acceptance or public deployment has been made by this work.

## Recommended next sequence after approval

The detailed decision matrix and safe local sequence are recorded in
[`BStudioB-HOSTING-APPROVAL-PLAN.md`](BStudioB-HOSTING-APPROVAL-PLAN.md).
The prepared host and DNS sheets are intentionally names-only and unapplied.
The Railway route is documented in
[`STAGING_RAILWAY_RUNBOOK.md`](STAGING_RAILWAY_RUNBOOK.md), but has not been
deployed.

1. Use the BStudioB-owned Render Free disposable route (`render.yaml`) as the
   no-cost fallback. Render authentication is still required in the open
   Chrome profile before the blueprint can be created; no payment is needed
   for the intended disposable staging shape.
2. Import a reviewed, permitted sample feed and verify freshness, attribution,
   stale-data behavior and operator audit logs.
3. Complete HTTPS, proxy, backup/restore and failure-mode checks; the local
   browser suite is now green, but hosted verification remains outstanding.
4. Select and migrate from SQLite before multi-worker production traffic.
5. Deploy the static showcase separately and only then consider a staged
   interactive subdomain rollout.
