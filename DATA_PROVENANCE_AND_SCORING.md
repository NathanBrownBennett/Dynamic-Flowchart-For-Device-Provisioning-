# Data provenance and scoring

Every displayed claim should be understandable to a domestic user and
auditable by a business or public-sector reviewer.

## Evidence states

- `measured`: produced by a controlled test with a recorded configuration.
- `independent_published`: published by an independent benchmark or authority.
- `vendor_claimed`: supplied by a manufacturer or seller and labelled as such.
- `specification_estimate`: derived from supplied hardware specifications; this
  is the current local heuristic benchmark state.
- `unknown`: no defensible evidence is attached.

The current security and performance numbers are comparison heuristics. They
are not certifications, penetration tests, warranty promises, patch-SLA
guarantees or a claim that a CPU family is currently vulnerable. Model-specific
vulnerability evidence must include a source, timestamp, matching identifier
and confidence.

## Ranking precedence

1. Eligibility for the selected context.
2. Security score and explicit security evidence quality.
3. Performance evidence and normalized capability.
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
