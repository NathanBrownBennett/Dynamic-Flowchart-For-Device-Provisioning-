# Milestone status and founder handoff

Date: 2026-08-26

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
  no custom domain or secret values.
- Render staging is live as the separate service
  `bstudiob-device-provisioning-staging` at
  `https://bstudiob-device-provisioning-staging.onrender.com`, deployed from
  commit `1904ba5` on the Free plan. This is separate from Buildy; no payment,
  upgrade or custom domain was added.
- Founder reports that the existing Railway workspace was downgraded to its
  Free plan. This preserves a no-cost staging option, but the plan, service
  health, persistence and public URL remain unverified from this worktree.
- Railway currently reports that the Free-plan resource-provisioning limit is
  exceeded, so a separate device-provisioning project cannot be created there
  without an upgrade. The existing Buildy project is intentionally not being
  reused.
- The current implementation pass adds context-aware Personal/Work/Government
  detail and comparison responses, business-role choices, score-version and
  evidence limitations, catalogue support/freshness/licence fields, and a
  guided domestic/small-business React workflow.
- Vite assets are explicitly served at `/assets/*` when the React bundle is
  mounted at the Flask root, covering the hosted same-service deployment path.
- The static showcase now provides a no-PII manual invite instruction without
  adding public account creation.
- The local React pilot has been visually refreshed to restore a stronger
  product identity: branded navigation, clearer hero hierarchy, decision
  snapshot, use-case cards, trust signals, responsive catalogue cards and a
  cleaner review surface. API and security boundaries are unchanged.
- The catalogue decision model now exposes transparent v2 score factors,
  security/OS/hardware/performance ratings, plain-English experience comments,
  and per-device hardening and performance guidance. Results are ordered by
  security score first, then performance, with price as a later tie-breaker.
- The validated catalogue feed now supports bounded `device_offers` records.
  Offers are HTTPS-only, retain check/expiry/source metadata, and are returned
  cheapest first with unknown prices last. The existing 34 CSV-backed records
  have real product names and specifications, but they do not have current
  approved vendor offers attached.
- When no approved offer feed is present, the UI shows vendor search links as
  unverified links and explicitly says that no live price has been supplied;
  it does not present demo prices or pretend that a search link is a quote.

## Render staging evidence (2026-08-20)

- Service status: Live; Docker runtime; one Free-plan service; no custom
  domain.
- `GET /healthz`: HTTP 200, `{"service":"device-provisioning-toolkit","status":"ok"}`.
- `GET /`: HTTP 200 and the React/Vite application shell is served.
- Response checks include HSTS, `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY` and a restrictive Permissions Policy.
- Render Free instances sleep when idle and the SQLite database is on `/tmp`;
  this is disposable staging only. Live scraping remains disabled.

## Verification completed

- Backend unit/security suite: 11 tests passed.
- Frontend API contract suite: 3 tests passed.
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
- The updated guided-flow browser suite: 7 tests passed, including domestic,
  business-role and Government context retention, plus decision-summary
  download coverage.
- The disposable sample-feed API smoke path passed for health, React root,
  criteria, catalogue status, source status and context-aware detail; reviewed
  evidence metadata was returned as expected.
- The refreshed frontend build passed visual browser verification locally;
  the Playwright suite remains 7/7 after updating its heading/footer selectors.
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
7. Approval of one or more permitted product/price providers, including API or
   affiliate terms, attribution, refresh cadence, currency/tax/delivery
   treatment and the credentials/worker arrangement needed to populate
   `device_offers`. Until this is approved and populated, current vendor price
   comparison is not complete.

No DNS, hosting account, provider integration, credential, payment, legal
acceptance or public deployment has been made by this work.

## Full-completion implementation pass (2026-08-26)

Implemented locally:

- Production defaults no longer bootstrap CSV, scraper or fallback data. The
  opt-in `ALLOW_SAMPLE_DATA=true` path is explicitly labelled as a local
  fixture; the default API returns an empty/unavailable catalogue until an
  approved feed is imported.
- Added `/readyz`, catalogue state (`empty`, `unavailable`, `sample`, `stale`,
  `partial`, `current`), current-offer counts, evidence coverage and provider
  descriptors to the versioned API.
- Added additive SQLite migrations for canonical product identity, provider
  offers, benchmark evidence, security evidence, support lifecycle and provider
  run records. Expired offers are excluded from current ranking and known
  total cost is the primary offer sort key.
- Added disabled-by-default provider contracts and worker boundaries for
  Icecat, affiliate/marketplace feeds, vulnerability evidence, manufacturer
  advisories and benchmark sources. No network adapter or credential value was
  added.
- React now labels evidence/freshness state, removes the hard-coded hero score,
  avoids showing catalogue prices as live prices, displays current vendor
  offers by total-known price, and calls out incomplete delivery data and
  affiliate/sponsored disclosures.
- Added `PROVIDER_INTEGRATION_PLAN.md`, `DATA_PROVENANCE_AND_SCORING.md` and
  `LIVE_CATALOGUE_OPERATIONS.md`; updated the architecture and environment
  contract.

Remaining blockers are external: provider terms/API approvals and credentials,
real permitted catalogue and offer data, managed durable storage, operator
authentication/roles, monitoring/backups, and hosted verification. The local
implementation is not production-ready and has not been deployed.

## Recommended next sequence after approval

The detailed decision matrix and safe local sequence are recorded in
[`BStudioB-HOSTING-APPROVAL-PLAN.md`](BStudioB-HOSTING-APPROVAL-PLAN.md).
The prepared host and DNS sheets are intentionally names-only and unapplied.
The Railway route is documented in
[`STAGING_RAILWAY_RUNBOOK.md`](STAGING_RAILWAY_RUNBOOK.md), but has not been
deployed.

1. Keep the separate Render Free service as the no-cost staging route. Do not
   treat it as production, add personal data, or enable mutation/operator
   controls.
2. Import a reviewed, permitted sample feed and verify freshness, attribution,
   stale-data behavior and operator audit logs.
3. Complete HTTPS, proxy, backup/restore and failure-mode checks; the local
   browser suite is now green, but hosted verification remains outstanding.
4. Select and migrate from SQLite before multi-worker production traffic.
5. Deploy the static showcase separately and only then consider a staged
   interactive subdomain rollout.
6. Import a reviewed live catalogue with vendor offers, verify freshness and
   stale-price behavior, then re-run the hosted browser and API acceptance
   checks before widening access.

## Bounded live retailer catalogue implementation (2026-08-26)

Implemented and locally verified:

- Replaced the disconnected legacy price path with a bounded staging-only
  retailer observation collector for fixed Amazon UK and John Lewis HTTPS
  search pages. Currys remains excluded because it rejects the bounded request;
  no bypass is attempted.
- Modernised Amazon title, decimal price, canonical product URL and explicit
  specification parsing; added deterministic John Lewis card parsing.
- Empty databases now populate from current observations when
  `ENABLE_LIVE_SCRAPING=true`, then refresh on a bounded background interval.
  Failed runs preserve the last catalogue.
- Observation records carry a 12-hour expiry, low-confidence `observed` state,
  source URL, condition, checked time and a prominent verify-on-retailer
  disclaimer. Retailer product-card images are retained only from explicit
  Amazon/John Lewis CDN hosts and served through the bounded same-origin image
  proxy; failed or missing images are labelled unavailable. Invented
  benchmark/security evidence is not stored.
- Public search and current-price endpoints now read the cached database only;
  they do not turn user input into outbound fetches. Offers are ordered by total
  known price.
- Local live bootstrap returned 24 current products/offers across laptop,
  tablet and desktop categories. The deterministic backend suite passes 13/13,
  frontend contract tests 3/3, Vite production build passes, Playwright passes
  8/8, Python compilation passes and `git diff --check` passes.

This mode is useful staging data, not a retailer-authorised API feed or a claim
of production readiness. Managed durable storage, formal retailer/provider
terms, real benchmark and vulnerability evidence, operator OIDC/roles, backups
and monitoring remain separate production gates.

## Security and result-integrity remediation (2026-08-26)

- Completed a standard repository security assessment covering the Flask/React
  request paths, catalogue ingestion, retailer observations, generated scripts,
  persistence and container boundary.
- Evidence-gated live ratings now show `Not rated` instead of turning retailer
  titles or unknown specifications into security/performance numbers.
- Retired render-on-read Graphviz detail handling, moved catalogue pagination
  ahead of evidence enrichment, bounded rate-limit state, constrained generated
  scripts and added strict feed date/evidence validation.
- Added partial-refresh preservation and non-root deterministic container builds.
- Backend tests pass 16/16, frontend contracts 3/3, Playwright passes 8/8,
  production frontend build and Python compilation pass, and Python/JavaScript
  runtime dependency audits report no known vulnerabilities.
- The public pilot remains staging-grade pending the production gates documented
  in `SECURITY_ASSESSMENT.md`.
