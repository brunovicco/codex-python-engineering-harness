# Changelog

All notable changes to the harness are documented here. Harness, development package, and plugin
versions are independent; see `docs/VERSIONING.md`.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the harness uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security

- Close the sensitive-file **read** gap: `validate_bash.py` (Bash/`exec_command`) and
  `guard_mcp.py` (MCP tool calls) now share the same sensitive-path denylist as
  `protect_sensitive_files.py` (apply_patch/Edit/Write) through a new `sensitive_patterns.py`
  module, so `.env`, credentials directories, SSH/AWS/Azure/gcloud config, `*.pem`/`*.key`
  files, and Terraform state cannot be read via shell commands or MCP filesystem tools either.
  Codex has no native `Read`/`Grep`/`Glob` function tools distinct from Bash/MCP (see
  `sensitive_patterns.py` for the upstream tool-coverage reference), so these two hook paths are
  the complete read/search/list surface.
- Fix a plugin/template divergence: the `python-engineering-harness` plugin's `hooks.json` never
  wired `protect_sensitive_files.py` into `PreToolUse` for `apply_patch`/`Edit`/`Write`, even
  though the script shipped in `plugins/python-engineering-harness/scripts/`. Projects bootstrapped
  from the plugin had no sensitive-file write protection at all until now.

### Changed

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
