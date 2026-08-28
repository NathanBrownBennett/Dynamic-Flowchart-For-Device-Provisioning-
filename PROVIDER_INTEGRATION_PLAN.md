# Provider integration plan

The toolkit is intentionally provider-neutral. No retailer scraping is part of
the production path and no provider credentials are stored in this repository.
The adapters in `integrations/` expose the boundary and return
`not_configured` until an operator has approved the provider terms, permitted
fields, rate limits, attribution, retention and secret-injection method.

## Source roles

| Need | Candidate source | What may be published | Gate |
| --- | --- | --- | --- |
| Product identity/specification/image | Icecat or manufacturer feed | identity, specs, licensed image and manual links | licence and attribution review |
| Identity verification | GS1 Verified by GS1 | internal GTIN/brand/model check | do not republish query results without permission |
| Consumer offers | Amazon PA-API UK, eBay Browse, Awin, CJ, impact.com | permitted offer fields, seller, total-known price, timestamp | account/API approval and affiliate disclosure |
| Vulnerability evidence | NVD/CPE, CISA KEV, MSRC and manufacturer advisories | model/OS-linked evidence and source link | matching quality and source terms |
| Independent benchmarks | Phoronix/OpenBenchmarking, licensed SPEC/UL results | suite, version, workload, score, test date and licence | benchmark licence and reproducibility review |
| Business/public-sector supply | manufacturer business feeds and approved distributors/VARs | quote/availability records, not consumer price claims | commercial account and procurement terms |

## Sources for operator review

- SerpApi Amazon Search API: https://serpapi.com/amazon-search-api
- OSV API: https://google.github.io/osv.dev/api/
- NVD data feeds: https://nvd.nist.gov/vuln/Data-Feeds
- CISA KEV catalogue: https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- eBay Browse API: https://developer.ebay.com/api-docs/buy/browse-api.html

Google Merchant API is not a competitor shopping feed: it is a merchant's own
catalogue boundary. Price aggregators such as PriceAPI or DataForSEO are
optional paid alternatives and require a separate legal, cost and data-quality
decision.

## Activation sequence

1. Approve one product identity source and one offer source for the UK region.
2. Record provider terms, attribution text, currency/tax/delivery treatment,
   refresh TTL, request budget and permitted retention.
3. Store only secret variable names in the host environment; never in feeds,
   tests, logs or source control.
4. Implement one adapter that emits the canonical product/offer contracts.
5. Validate identity collisions and HTTPS source URLs, then import atomically.
6. Observe provider failures in `provider_runs`; retain last-known records only
   until their explicit expiry, then hide them from current price ranking.
7. Verify hosted API, frontend, attribution and stale-data behavior before any
   wider access.

## Current adapter state

The opt-in NVD, CISA KEV and OSV adapters are implemented in
`integrations/providers.py`. They use fixed HTTPS endpoints, bounded response
sizes, no redirects and timeouts. They return normalized evidence candidates
only; they do not automatically attach a vulnerability to a device. An
operator must match the exact product/OS/package and import a reviewed feed.

The opt-in SerpApi Amazon UK and eBay Browse adapters are also implemented.
They emit a bounded, validated catalogue draft containing offer links, prices,
availability and provider-returned images. They do not infer operating systems,
benchmarks, support dates or security ratings. SerpApi's free plan is a small
development allowance rather than unlimited free infrastructure; eBay Buy API
production access and both providers' terms, attribution and retention rules
must be approved before activation. Amazon PA API and affiliate feeds remain
separate provider options and remain disabled until their account/terms
requirements are met.

Use `scripts/fetch_provider.py` to create a local draft, then review it and
import it only with `scripts/import_catalogue.py`. The provider endpoint never
replaces the catalogue automatically and no provider key is returned in a
record or written to a feed.

The local fixture feed is for deterministic testing only. It is not a live
catalogue and must not be represented as one.
