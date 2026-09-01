# Catalogue data-quality assessment

This document records how the toolkit decides whether a comparison is
evidence-backed. It is a release gate, not a scorecard for inventing missing
facts.

## Current live assessment

The public API was checked on 2026-09-01. It reported 24 products, 24 current
observed offers and 24 product images. Each product currently has one observed
John Lewis offer; that is useful availability context but is not a multi-vendor
market comparison. Amazon, Currys and other vendor links remain search links
unless an approved offer record supplies a price, timestamp and permitted
attribution.

The same response reported 0/24 products with model-linked security evidence
and 0/24 with sourced benchmark evidence. The current records therefore stay
unrated for security and performance. This is intentional: retailer titles,
RAM, storage and processor fields can explain likely hardware trade-offs, but
they do not prove a device security baseline or a benchmark result.

The live catalogue is therefore **not release-ready for evidence-backed
rankings**. It is a current retailer-observation pilot with visible evidence
gaps.

## Release gates

`integrations/quality.py` and `scripts/profile_catalogue.py` measure these
gates for every product:

- identity is complete and has no duplicate brand/model/region key;
- the product source is attributed and current;
- every product has a current offer;
- every product has at least two current vendors;
- the operating system is explicit and supported;
- security evidence is model-linked, attributed and timestamped;
- the support lifecycle matches the explicit operating system and remains
  attributable and current;
- the benchmark is measured or independently published, attributed and
  timestamped.

The API exposes the same counts, gates and blocking issues under
`/api/v1/catalogue/status.data_quality`. The public UI displays them beside
the catalogue so users can see why a rating is present or withheld.

## Safe completion path

To complete the comparison without fabricating data, an operator must enrich
the reviewed Google Sheet rows with approved records for each exact model:

1. Add at least two permitted vendor offers, including total-known price,
   currency, availability, checked time, expiry, product URL, seller and
   affiliate/sponsorship status where applicable.
2. Add a model-specific benchmark from a source whose publication or licence
   permits this use. Record suite, version, workload, score, test date,
   evidence type, URL, licence and confidence.
3. Add model/platform security evidence from an authoritative advisory or
   CPE/CVE mapping, with affected/fixed versions, checked time and source URL.
4. Add a support-lifecycle record whose operating system exactly matches the
   product’s explicit OS, with the manufacturer source and end date.
5. Run the feed validator and `python scripts/profile_catalogue.py --strict`
   against the staged database before considering publication. Run the
   frontend checks with `cd frontend && npm test && npm run build`.

The provider adapters for Amazon, eBay, affiliate networks, NVD/OSV/CISA and
benchmark sources are deliberately disabled until terms, permitted fields,
rate limits, attribution and credentials are approved. No API key or affiliate
tracking identifier belongs in this repository.
