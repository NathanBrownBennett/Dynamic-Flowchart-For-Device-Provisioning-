# Local staging and sample-feed acceptance

Date of this record: 2026-08-19

This is a disposable local acceptance record. It does not approve hosting,
DNS, provider access, credentials or publication.

## Feed under test

- File: `catalogue-feed.example.json`
- Source label: `Approved product feed name`
- Remote URL: metadata only; the import path does not fetch it.
- Product count: 1
- Live scraping: disabled

## Acceptance checks

1. Start Flask with a temporary `DATABASE_PATH`, `SERVE_FRONTEND_AT_ROOT=true`
   and a loopback `PORT`.
2. Confirm `/healthz` returns `status=ok`.
3. Import the sample feed with:

   ```sh
   DATABASE_PATH=STAGING_DATABASE_PATH \
     python scripts/import_catalogue.py --feed catalogue-feed.example.json
   ```

4. Confirm `/api/v1/catalogue/status` reports the imported source and one
   product, with `live_scraping=false`.
5. Confirm `/api/v1/devices` exposes the catalogue source and retrieval fields.
6. Stop and restart the local process against the same temporary database;
   confirm the imported catalogue remains available.
7. Validate a malformed feed without importing it; confirm the last good
   catalogue remains unchanged.
8. Confirm the root response serves the React bundle and `/api/v1/healthz`
   remains available from the same Flask process.

## Recorded result

The sample feed imported successfully into a temporary SQLite database. The
local process returned healthy status, served the React bundle, exposed the
versioned API and reported scraping disabled. A restart-preservation and
malformed-feed atomicity check was run against a disposable database; both
passed. No remote URL was fetched.

The test suite also covers protected catalogue import validation and the
versioned API contract. A future hosted pilot must repeat these checks after
the selected host, persistent volume, access policy and approved feed source
are explicitly recorded.

## Browser verification update

After installing the local Playwright Chromium dependency, `npm run test:e2e`
passed all 7 browser tests against the disposable local staging server. This
does not approve a hosted deployment or change the founder gates.
