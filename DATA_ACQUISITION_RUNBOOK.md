# Evidence and catalogue acquisition runbook

Status: implementation-ready, source activation gated

This runbook defines the records required before the toolkit can publish a
ranked, live recommendation. It is intentionally separated from the public
request path: providers run in an operator-controlled job, produce a reviewed
JSON feed, and the feed is imported atomically.

## What is required for each product

Every product needs:

- exact brand, model, variant and UK-region identity;
- a permitted catalogue source and HTTPS attribution URL;
- an approved image licence or no image;
- current offer records from at least two permitted vendors where comparison
  is advertised, including seller, condition, item price, delivery price,
  total-known price, currency, stock state, checked time and expiry;
- an explicit operating system, not one inferred from brand or product family;
- an official support-lifecycle record for that OS/model;
- an independent or controlled benchmark record before a performance score;
- model-matched security evidence before a security score.

Missing evidence remains missing. The application must not fill these fields
from product titles, RAM, CPU GHz, search links or retailer assumptions.

## Source decisions

### Offers and product data

- Amazon Product Advertising API UK is the preferred Amazon route. It requires
  an Associates account and API credentials; do not use page scraping as a
  substitute.
- eBay Browse API is a possible second marketplace route. It requires an
  application access token, and production use is subject to eBay programme
  approval and conditions.
- Awin, CJ or impact.com may supply affiliate feeds only after their permitted
  fields, attribution, retention and commercial terms are approved.
- Currys and John Lewis remain disabled in production until an authorised feed
  or written permission for the chosen access method exists. The existing
  observation collector is staging-only and low-confidence.

### Security evidence

- NVD CVE/CPE data and the CISA Known Exploited Vulnerabilities feed are useful
  public sources, but a CVE must be matched to the exact product/OS/CPE before
  it is attached to a product.
- Manufacturer advisories are the source of truth for affected versions and
  fixes where available. Store the advisory URL and checked timestamp.
- A generic OS CVE is not model-specific evidence and must not unlock a device
  score by itself.

### Support lifecycle

Use official manufacturer lifecycle pages or an approved business feed. Record
the exact OS/model scope, end-of-support or end-of-servicing date, patch
cadence, source URL, checked time and confidence. A platform-level date must
not be presented as a model guarantee unless the source explicitly covers that
model. For example, Microsoft publishes model-specific Surface firmware and
driver dates separately from the Windows lifecycle.

### Benchmarks

Use a controlled internal test or an independent published result whose licence
allows reuse. Record suite, version, workload, score, test configuration, test
date, source URL, licence and confidence. Scores from different suites must not
be compared without a documented normalization method. A CPU speed/RAM/storage
formula is not a benchmark.

## Safe activation sequence

1. Approve the sources, terms, attribution, retention and refresh budget.
2. Inject credentials into the host only as environment variables. Never place
   them in this repository, feeds, logs or tickets.
3. Run a provider job outside the browser request path.
4. Resolve every offer to a canonical product identity; reject collisions and
   ambiguous variants.
5. Run the read-only quality profile:

   ```bash
   python scripts/profile_catalogue.py --database /path/to/catalogue.db
   ```

6. Review the JSON feed and source links manually.
7. Import only after review:

   ```bash
   python scripts/import_catalogue.py --feed /path/to/approved-feed.json
   ```

8. Verify `/readyz`, `/api/v1/catalogue/status`, stale expiry, vendor ordering,
   evidence attribution and the browser journeys.

### Optional free/developer sources currently wired

- `serpapi_amazon`: SerpApi Amazon UK structured search. Configure only
  `SERPAPI_API_KEY`, `SERPAPI_AMAZON_SEARCH_TERM` and optionally
  `SERPAPI_RESULT_LIMIT`. The free plan is limited and provider/Amazon terms
  govern display, caching and image use.
- `ebay_browse`: eBay Browse API UK search. Configure only
  `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`, `EBAY_SEARCH_TERM` and optionally
  `EBAY_RESULT_LIMIT`. It uses application OAuth and remains subject to eBay
  production approval and API terms.
- `osv`: OSV.dev package vulnerability lookup. Configure
  `OSV_PACKAGE_NAME`, `OSV_ECOSYSTEM` and optionally `OSV_PACKAGE_VERSION`.
  This is software evidence and cannot unlock a hardware/device rating.

These providers are run with the operator-only job boundary:

```bash
python scripts/fetch_provider.py --provider serpapi_amazon --output /tmp/serpapi-amazon-feed.json
python scripts/fetch_provider.py --provider ebay_browse --output /tmp/ebay-feed.json
```

The output is a review draft. It is not live until an operator reviews source
links, identity matches, image rights, currency/delivery treatment, freshness,
terms and the quality profile, then performs an explicit catalogue import.

## Release gates

`profile_catalogue.py --strict` is intentionally expected to fail until every
product has current offers, two vendors, an explicit OS, support lifecycle,
security evidence and benchmark evidence. This is a data-quality gate, not a
claim that those sources are currently available.

The current application remains safe to run without these records: it shows
the catalogue state and withholds unsupported ratings.

## Optional Google Sheets source

For a free invite-only pilot, a BStudioB-owned Google Sheet can act as the
review surface. Publish only the non-personal `Catalogue` tab as CSV and set
the names-only host variables documented in
[`GOOGLE_SHEETS_CATALOGUE.md`](GOOGLE_SHEETS_CATALOGUE.md). The application
fetches it only over HTTPS, without redirects, with bounded bytes/rows and a
six-hour in-process refresh window. It validates the complete feed before
atomic replacement and preserves the previous catalogue after any failure.

This is not private-sheet integration: a public CSV export is public data. Do
not put credentials, operator notes, customer information or purchase data in
the published tab. The source still cannot authorise retailer scraping or
unlock ratings without the evidence fields and licences described above.

## Sources for operator review

- NVD data feeds: https://nvd.nist.gov/vuln/Data-Feeds
- CISA KEV catalogue: https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- eBay Browse API: https://developer.ebay.com/api-docs/buy/browse-api.html
- eBay API requirements: https://developer.ebay.com/api-docs/buy/buy-requirements.html
- Amazon PA API registration: https://affiliate-program.amazon.co.uk/help/topic/api/registration
- Microsoft Surface lifecycle: https://learn.microsoft.com/en-us/surface/surface-driver-firmware-lifecycle-support
