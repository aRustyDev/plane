<!-- woven: fork-specific security policy. This is the aRustyDev/plane fork ("Open-EE") of the
     upstream makeplane/plane Community Edition. Reports for THIS fork's changes go through the
     fork's GitHub private vulnerability reporting; upstream Plane issues go to upstream. plane-7fn.4.9 -->

# Security policy

This repository is the **`aRustyDev/plane` ("Open-EE") fork** of the upstream
[`makeplane/plane`](https://github.com/makeplane/plane) Community Edition. This policy covers
security issues in **this fork's changes** (the Woven "Open-EE" additions — OIDC SSO, CI/CD, and
related work). Vulnerabilities in unmodified upstream code should also be reported upstream via
[Plane's policy](https://github.com/makeplane/plane/security).

## Reporting a vulnerability

**Please do not open a public issue for security problems.** Report privately through GitHub's
**private vulnerability reporting**:

- Go to the **[Security tab → "Report a vulnerability"](https://github.com/aRustyDev/plane/security/advisories/new)**,
  which opens a private advisory visible only to the maintainers.

Include enough detail to reproduce and assess the issue: affected component/endpoint, version or
commit, reproduction steps, and impact.

Please practice responsible disclosure:

- Keep the report confidential until a fix is available and coordinated.
- Do not run automated scans against any hosted deployment without prior consent.
- Do not exploit a finding beyond what is necessary to demonstrate it, and never access or modify
  data that isn't yours.
- No social engineering, DoS/DDoS, spam, or attacks on third-party services.

## Out of scope

- Vulnerabilities requiring man-in-the-middle or physical access to a user's device.
- Content spoofing / text injection without a demonstrable attack vector.
- Email spoofing; missing DNSSEC/CAA/CSP headers.
- Absence of secure / HTTP-only flags on non-sensitive cookies.

## Supply-chain assurances

Release images are published to `ghcr.io/arustydev/plane-*` and are, per release, **cosign-signed
by digest** (keyless via GitHub OIDC), carry a **SLSA build-provenance** attestation and an
**SPDX SBOM** attestation, and are scanned with **trivy**. Verify before deploying — see the
verification commands in `.github/workflows/woven-build.yml`.

## Handling

This is a community fork maintained on a best-effort basis; there is no guaranteed response SLA.
Reports are triaged as promptly as capacity allows, and reporters who wish to be credited will be
acknowledged once an issue is resolved.
