# DNS and TLS change sheet — names only

Status: prepare-only. This sheet describes the change that may be requested
after founder approval. It does not create or validate a DNS record.

## Proposed record names

- `PROVISIONING_SUBDOMAIN`
- `DNS_RECORD_TYPE`
- `HOSTING_PROVIDER_DNS_TARGET`
- `DNS_TTL`
- `TLS_CERTIFICATE_MODE`
- `TLS_CERTIFICATE_OWNER`

Proposed public hostname label: `provisioning` under the approved BStudioB
domain. The exact domain, record target, TTL and certificate owner must be
filled in by the authorised operator using the selected host's instructions.

## Pre-change checks

- `FOUNDER_DNS_APPROVAL_ID`
- `FOUNDER_HOSTING_APPROVAL_ID`
- `HOSTING_SERVICE_HEALTHCHECK_PATH`
- `HOSTING_SERVICE_PUBLIC_ACCESS_POLICY`
- `HOSTING_SERVICE_ROLLBACK_PLAN`

Required health path: `/healthz`. The interactive application must remain
invite-only and must not expose operator mutation routes publicly.

## Post-change checks

- `DNS_RESOLUTION_CHECK`
- `TLS_CERTIFICATE_CHECK`
- `HTTPS_REDIRECT_CHECK`
- `SECURITY_HEADERS_CHECK`
- `INVITE_ONLY_ACCESS_CHECK`
- `PUBLIC_ADMIN_ROUTE_CHECK`

Expected result for `PUBLIC_ADMIN_ROUTE_CHECK`: operator routes remain
protected or disabled. Do not record IP addresses, tokens, certificate
private keys or other credentials in this repository.
