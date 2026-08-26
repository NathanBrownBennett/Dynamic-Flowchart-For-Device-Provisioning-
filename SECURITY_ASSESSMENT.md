# Security and results assessment

Assessment date: 2026-08-26. Scope: Flask API, React client, retailer observation
pipeline, SQLite persistence, generated hardening scripts and container runtime.

## Remediated findings

- Legacy device-detail requests now redirect to the cached React/API view and no
  longer invoke Graphviz on every public request.
- Live security scores require an explicit OS, model-specific security evidence
  and support lifecycle. Retailer names and inferred platform labels cannot
  create a security score.
- Live performance scores require sourced benchmark evidence. Specification
  capacity is not represented as benchmark performance.
- Catalogue filtering and pagination occur in SQL before bulk evidence loading,
  removing full-catalogue and per-device evidence-query amplification.
- Hardening scripts accept only exact supported OS and task identifiers, reject
  unsafe filename input, and fail visibly when required Linux controls fail.
- Feed timestamps and freshness windows are parsed, normalized and bounded.
  Generic operator feeds cannot self-assert verified/high-confidence status.
- An anomalously small retailer refresh preserves the previous catalogue.
- Rate-limit state is bounded and mutation endpoints share the request guard.
- The runtime image uses deterministic frontend installs and a non-root user.
- Runtime pins were upgraded to Flask 3.1.3, Requests 2.34.2, Werkzeug 3.1.8
  and urllib3 2.7.0 after dependency audit findings in the prior pins.
- The legacy broad `requirements.txt` environment freeze was replaced by the
  seven dependencies the web service actually needs; its 25 vulnerable,
  unrelated package families are no longer part of the non-Docker install.

## Result integrity

Retailer observations may provide a current product title, observed price and
vendor URL. They do not prove the exact OS, firmware, support lifecycle,
vulnerability exposure, benchmark performance, stock or final delivered price.
The UI therefore displays `Not rated` until the required evidence is attached.

## Remaining production gates

The public pilot is not production-ready. It still needs managed PostgreSQL and
backups, shared/provider-level rate limiting, operator OIDC and roles, a separate
background worker, monitoring and alerting, approved data-source/licensing terms,
and model-matched benchmark/security/support feeds.
