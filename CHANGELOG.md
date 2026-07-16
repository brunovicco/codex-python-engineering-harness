# Changelog

All notable changes to the harness are documented here. Harness, development package, and plugin
versions are independent; see `docs/VERSIONING.md`.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the harness uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Pin GitHub Actions and generated service container images to immutable SHAs and digests.
- Add Docker image updates to Dependabot and verify pins for every supported Python version.

## [1.2.0] - 2026-07-16

### Added

- Optional governance capability profiles and regulatory overlays.
- Vendor-neutral OpenTelemetry observability boundaries for generated services.
- Service, library, and empty virtual-workspace generation profiles.
- Non-destructive merge and drift checking for generated projects.
- Public security and supported-version policy.
- Upgrade and versioning documentation.
- Complete repository quality gate in CI.
- Dependabot updates for GitHub Actions and Python dependencies.
- Five-minute evaluation and profile comparison.

[Unreleased]: https://github.com/brunovicco/codex-python-engineering-harness/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/brunovicco/codex-python-engineering-harness/releases/tag/v1.2.0
