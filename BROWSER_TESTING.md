# Browser testing requirements

The deterministic API/frontend checks do not require a browser. The Playwright
end-to-end suite does, and it is intentionally separate from the normal
non-Docker Flask staging check.

## Local setup

From the repository root, install the Node dependencies and the pinned
Playwright Chromium browser:

```sh
npm ci
npx playwright install chromium
```

On a clean Linux host, Playwright may also require its documented system
dependencies. Use the host-approved package installation method; do not add
those OS packages to this repository.

Run the suite with:

```sh
npm run test:e2e
```

The configured test server uses a disposable database path and binds to
`127.0.0.1:8012`. It does not require Docker, a public URL, DNS, credentials
or live retailer access.

## Current local status

The Playwright Chromium prerequisite has now been installed in the local
environment and `npm run test:e2e` passes all 7 tests. The suite runs against
the disposable local staging server; it does not establish hosted or
production readiness. The backend security suite, frontend API contract suite,
Python compilation and Vite build also pass.

Do not use a headed browser or a public deployment as a substitute for this
local check. Hosted verification still requires the founder-approved host,
access policy, HTTPS and persistent storage boundary.
