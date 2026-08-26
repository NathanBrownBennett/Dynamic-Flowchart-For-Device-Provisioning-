# Data provenance and scoring

Every displayed claim should be understandable to a domestic user and
auditable by a business or public-sector reviewer.

## Evidence states

- `measured`: produced by a controlled test with a recorded configuration.
- `independent_published`: published by an independent benchmark or authority.
- `vendor_claimed`: supplied by a manufacturer or seller and labelled as such.
- `specification_estimate`: derived from supplied hardware specifications. It
  is allowed only in local fixtures and is never displayed as a live benchmark.
- `unknown`: no defensible evidence is attached.

Live security ratings are withheld unless the exact OS, model-specific security
evidence and support lifecycle are all present. Live performance ratings are
withheld unless a measured or independently published benchmark includes a
source, timestamp and normalized score. Retailer titles, brand names and raw
RAM/storage capacity cannot create either rating. Any displayed rating remains
a comparison aid, not certification, penetration-test evidence or a patch SLA.

## Ranking precedence

1. Eligibility for the selected context.
2. Rated security evidence; unrated products sort after rated products.
3. Sourced performance evidence; unrated products sort after rated products.
4. Verified current total-known offer price.
5. Stable model-name tie-breaker.

Affiliate, sponsored and preferred-vendor flags never add ranking points.
Unknown prices sort after known prices. Expired offers are not returned as
current offers. A price without delivery data is labelled as incomplete rather
than presented as a guaranteed basket total.

## User-facing language

Plain-English guidance explains what the score means, what it cannot prove,
and the first hardening/performance steps. Government and business views are
decision aids only; actual enrolment, policy enforcement and procurement stay
inside an authorised tenant, MDM or purchasing workflow.
