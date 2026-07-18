# Changelog

All notable changes to the harness are documented here. Harness, development package, and plugin
versions are independent; see `docs/VERSIONING.md`.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the harness uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Add an explicit `uv lock --check` CI step before every `uv sync --frozen` step (repository, generated profiles, template, and library/workspace profile workflows) and document it as the first setup command in README.md, template/AGENTS.md, template/README.md, and profiles/*/README.md, so lockfile drift from `pyproject.toml` fails fast instead of silently installing stale dependencies. The repository and template `quality_gate.py` scripts already ran `uv lock --check` as their first check.
- Add a feature-freeze notice to the top of CONTRIBUTING.md: the shared core only accepts bug/security/documentation fixes while it is consolidated with its sibling harness into a unified harness.
- Pin GitHub Actions and generated service container images to immutable SHAs and digests.
- Add Docker image updates to Dependabot and verify pins for every supported Python version.
- Add community health policies, structured issue forms, a pull-request checklist, and public
  contribution and support guidance.

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
