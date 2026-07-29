# Changelog

All notable changes to the Woven Plane fork are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Releases are
managed by [release-please](https://github.com/googleapis/release-please); entries are grouped
as Added / Changed / Deprecated / Removed / Fixed / Security.

## [1.4.2](https://github.com/aRustyDev/plane/compare/v1.4.1...v1.4.2) (2026-07-29)


### Fixed

* **ci:** apply severity filter to trivy gate exit-code (limit-severities-for-sarif) ([#37](https://github.com/aRustyDev/plane/issues/37)) ([99de953](https://github.com/aRustyDev/plane/commit/99de953eaad3157816bde17d4254bd3ca6df29b7))
* **ci:** run grype even when trivy gates; harden SARIF uploads ([#35](https://github.com/aRustyDev/plane/issues/35)) ([f2b606e](https://github.com/aRustyDev/plane/commit/f2b606e48da1539e607c316d1d54cb8ea1d3e6d8))
* **ci:** unblock Dependabot PRs (format latent file + ignore override-pinned deps) ([#26](https://github.com/aRustyDev/plane/issues/26)) ([1cbe481](https://github.com/aRustyDev/plane/commit/1cbe4810365373c4350b9b93bf950957a656b27d))
* **deps:** patch vulnerable library deps to clear the release gate ([#38](https://github.com/aRustyDev/plane/issues/38)) ([5db5d89](https://github.com/aRustyDev/plane/commit/5db5d89395579fcf432afab0737adbd701f0dd33))
* **deps:** pin core prosemirror packages to dedupe editor build ([#28](https://github.com/aRustyDev/plane/issues/28)) ([1c6f578](https://github.com/aRustyDev/plane/commit/1c6f578623f5f43835e776094d7769412dbeafac))
* **deps:** regenerate corrupted pnpm-lock.yaml (duplicate mapping key) ([#33](https://github.com/aRustyDev/plane/issues/33)) ([3647f11](https://github.com/aRustyDev/plane/commit/3647f11a89b829624d348a44447c8b890fb0ef40))

## [1.4.1](https://github.com/aRustyDev/plane/compare/v1.4.0...v1.4.1) (2026-07-28)


### Fixed

* **woven:** attest SBOM via actions/attest-sbom (referrer, not cosign .att tag) ([#12](https://github.com/aRustyDev/plane/issues/12)) ([a4b871f](https://github.com/aRustyDev/plane/commit/a4b871f3c682ef9f96607dfb58e7a39f8fe761bd))

## [1.4.0](https://github.com/aRustyDev/plane/compare/v1.3.1...v1.4.0) (2026-07-27)


### Added

* **auth:** OIDC SSO - provider, views, instance config ([74b9854](https://github.com/aRustyDev/plane/commit/74b98540bcddf7a108d37d093966d05143766075))
* **oidc:** add generic OIDC SSO provider + adapter (plane-07r) ([c36c943](https://github.com/aRustyDev/plane/commit/c36c943c249e8d1176dd26da5449d9524b2e6ec8))
* **oidc:** admin OIDC config form + login "SSO" button (plane-5kc) ([#2](https://github.com/aRustyDev/plane/issues/2)) ([f2aa51d](https://github.com/aRustyDev/plane/commit/f2aa51dc3f0287e073aa18508978262b923f45b5))
* **oidc:** register OIDC config + expose is_oidc_enabled (plane-4cr) ([0153ff5](https://github.com/aRustyDev/plane/commit/0153ff51bb7b13f1068a4125c39de8e36ac52864))
* **oidc:** wire OIDC auth views + routes (plane-1f2) ([58a2662](https://github.com/aRustyDev/plane/commit/58a266240ca05c12abe5d48e8ae1b6a1fbc54804))

## [1.3.1] - 2026-05-15

Fork baseline — Plane Community Edition v1.3.1 (upstream `makeplane/plane`). Woven "Open-EE"
changes (starting with OIDC SSO) are recorded from the next release onward.

[1.3.1]: https://github.com/aRustyDev/plane/releases/tag/v1.3.1
