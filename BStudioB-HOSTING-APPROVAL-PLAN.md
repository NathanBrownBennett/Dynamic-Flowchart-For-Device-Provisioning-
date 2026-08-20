# BStudioB Device Provisioning Toolkit — hosting approval plan

Date: 2026-08-19

This plan separates the work that can be completed locally from decisions that
create an external cost, legal commitment, public exposure, or security
boundary. The recommended launch is an invite-only pilot, not a public
self-service service.

## Decision 1 — hosting

**Recommendation:** use a BStudioB-owned low-cost application host for the
Flask service, with the static showcase served independently. Keep the first
deployment single-instance and non-Docker so the existing Gunicorn/Procfile
path is easy to diagnose. Do not use the personal Railway project as
production.

**Pilot shape:** one service, one persistent volume, SQLite catalogue,
`ENABLE_LIVE_SCRAPING=false`, no public mutation routes, and a private or
invite-only access layer. Move to managed Postgres only when concurrent users
or multiple workers justify it.

**Founder gate:** select the provider/account and approve any paid resource.

## Decision 2 — subdomain and TLS

**Recommendation:** `provisioning.bstudiob.co.uk` for the controlled pilot.
The apex company site remains the public marketing boundary; the toolkit
showcase can link to the subdomain only after access controls pass.

**Founder gate:** approve the DNS record and hosting-generated TLS certificate.
No DNS change is made by this plan.

## Decision 3 — catalogue and retailer data

**Recommendation:** begin with a reviewed, versioned BStudioB-owned sample
catalogue (`catalogue-feed.example.json`). Every item must record source,
retrieved date, freshness window, attribution and permitted image/license
status. Keep live scraping disabled until each source has an approved API or
written terms review.

**Founder gate:** approve the sources, fields, refresh frequency, attribution,
affiliate disclosures and image licences.

## Decision 4 — operator authentication

**Recommendation:** do not expose the current bearer-token mutation gate to
the public internet. For the pilot, put the service behind a host access
control layer or an authenticated company-only gateway, while retaining the
backend token only for local/staging automation. Before public operator use,
add session authentication, CSRF protection, audit logging and secret
injection through the host secret manager.

**Founder gate:** choose the identity provider and approve the operator list.
Never place a token in source control, browser code or a task document.

## Decision 5 — persistence, jobs and recovery

**Recommendation:** single-instance persistent SQLite for the invite-only
pilot; scheduled/manual catalogue imports; no live scraper or background
worker. Before any public or multi-instance launch, migrate to managed
Postgres, add a queue/cache, encrypted object/database backups, restore tests,
retention limits, error metrics and alerts.

**Acceptance checks:** restart preserves catalogue; malformed import is atomic;
backup restores into a disposable environment; stale data is visible; failed
refresh does not replace the last good feed.

## Decision 6 — licensing and public claims

**Recommendation:** publish only the static showcase initially. Describe the
interactive app as an invite-only evaluation. Preserve the repository's
licence/IP review gate, retailer attribution, image licence evidence and
no-guarantee wording. Do not claim official retailer affiliation.

**Founder gate:** confirm chain of title/licence and approve the public copy
before publication.

## Approved safe implementation sequence

1. Keep the current working-tree implementation and run the local test/build
   suite.
2. Add a staging configuration checklist and sample-feed acceptance record.
3. Install the pinned Chromium dependency and run the browser suite when the
   machine permits it.
4. Verify health, API read paths, import atomicity, proxy restrictions and
   frontend build in a disposable local environment.
5. Prepare, but do not apply, the host environment variable list and DNS/TLS
   change sheet.
6. After the founder gates above are explicitly approved, deploy an isolated
   staging service, run the smoke/restore checks, and only then request a
   production pilot publication.

## Current approval state

The local engineering sequence is approved to continue. Hosting selection,
DNS/TLS, data-source terms, operator identity, production persistence,
licensing, and public publication remain **not approved** until their specific
founder decisions are recorded.
