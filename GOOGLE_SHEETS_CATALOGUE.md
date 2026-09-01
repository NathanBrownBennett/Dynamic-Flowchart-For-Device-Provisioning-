# Google Sheets catalogue source

This is an optional free persistence path for the invite-only pilot. The
application does not authenticate to Google and does not store a Google
credential. An operator maintains a reviewed, non-personal product catalogue
in a BStudioB-owned Google Sheet and publishes only its `Catalogue` tab as a
CSV export. Render reads that export over HTTPS and imports it into its local
SQLite cache after full validation.

## Sheet layout

Use [`catalogue-google-sheet-template.csv`](catalogue-google-sheet-template.csv)
as the column contract. One row is one canonical product identity. Keep nested
offers, benchmark evidence, security evidence and support lifecycle records in
the corresponding JSON columns. The JSON must contain only public catalogue
data and HTTPS source links. Do not put names, emails, addresses, credentials,
purchase records or other personal data in the sheet.

To seed or update a local export before uploading it to the Sheet, use:

```bash
python scripts/export_catalogue_for_google_sheet.py \
  --database /path/to/devices.db \
  --output /tmp/device-provisioning-catalogue.csv
```

Review the CSV manually before uploading. The export preserves missing evidence
as empty fields; it does not generate scores.

The app will not publish ratings merely because a row contains a number. A
benchmark must be `measured` or `independent_published`; security evidence and
support lifecycle records must be model/OS matched, attributed and current.
Incomplete rows remain visible but unrated.

## Configure the free path

1. Create or maintain the private BStudioB-owned Sheet and review every row.
2. Publish only the catalogue tab as CSV. Do not publish any tab containing
   operator notes or private information.
3. Set these names-only environment values in the host:

   ```text
   GOOGLE_SHEETS_AUTO_SYNC=true
   GOOGLE_SHEETS_CSV_URL=https://docs.google.com/spreadsheets/d/<id>/export?format=csv&gid=<catalogue-tab-id>
   GOOGLE_SHEETS_SOURCE_NAME=BStudioB reviewed catalogue
   GOOGLE_SHEETS_SYNC_TTL_MINUTES=360
   ```

4. The first catalogue/status or device request after the TTL fetches the
   published CSV once per service process. The current good SQLite catalogue
   remains in place if Google is unavailable, redirects, exceeds limits, or
   fails validation.

For a controlled manual refresh, set `PROVISIONING_ADMIN_TOKEN` in the host
secret manager and POST to `/admin/catalogue/sync-google-sheet` with a bearer
token. Do not expose that token in frontend code or source control.

## Trade-offs and launch boundary

This avoids a paid database and avoids a Google API credential, but a published
CSV is public and must contain only data intended for public display. It is
eventually consistent, not a transactional database, and the Render Free
instance still loses its SQLite cache when recycled. It therefore supports a
free invite-only pilot, not durable production storage or multi-instance
concurrency. Move to managed Postgres/object storage and a scheduled worker
when the catalogue or traffic requires it.

The Google Sheet is a source of reviewed data, not permission to scrape Amazon,
Currys or another retailer. Retailer/API terms, affiliate disclosure, image
licensing and benchmark permissions remain separate approval gates.
