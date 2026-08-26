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

The local fixture feed is for deterministic testing only. It is not a live
catalogue and must not be represented as one.
