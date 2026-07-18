# Changelog

All notable changes to the harness are documented here. Harness, development package, and plugin
versions are independent; see `docs/VERSIONING.md`.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the harness uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Phase 0-1 (report-only) Evidence-Gated Engineering Loop foundation, see `docs/LOOPS.md`:
  - `.loop/**` and `scripts/loop_*` are now denylisted for agent writes in
    `protect_sensitive_files.py` (template and plugin), so an agent cannot silently build
    `loop_runner.py`/`loop_gate.py`/`loop_state.py` or populate `.loop/` ahead of schedule.
  - `template/scripts/_vendor_loop_schemas/` vendors the contract validator from
    `brunovicco/engineering-loop-schemas` (pinned commit recorded in each vendored file's
    header); `template/scripts/validate_loop_contracts.py` wires it into the generated
    project's quality gate as a new `loop-contracts` check that is a documented no-op until
    a human places a contract under `.loop/contracts/`.
  - `.github/workflows/loop-self-evaluation.yml` (`workflow_dispatch` + weekly schedule):
    renders every profile/governance-profile combination, gates each one, checks
    manifest/plugin/documentation consistency, and uploads a JSON + Markdown report as a
    build artifact. It never modifies repository code; its optional agent-interpretation
    step is disabled by default and defines no credentials. Minimal per-job permissions,
    `persist-credentials: false`, and full-SHA-pinned actions throughout.

### Fixed

- The vendored `_vendor_loop_schemas/models.py` failed CI lint on the generated-profiles
  Python 3.14 job: ruff's `UP037` flagged the module's load-bearing quoted self-referencing
  `from_dict` return annotations (e.g. `-> "Budgets"`) as removable, because it assumes PEP
  649 lazy-annotation semantics whenever the caller's own `target-version` is `py314` --
  correct in isolation, wrong here since the quotes are required on Python 3.12/3.13, which
  this vendored file also has to support. Re-vendored from
  `brunovicco/engineering-loop-schemas@75a63eef269fd995128ab39c89e551fe58a27bf7`, which
  suppresses `UP037` via a `[tool.ruff.lint.per-file-ignores]` entry rather than an inline
  `# noqa` (an inline noqa becomes a *second* failure, `RUF100` unused-directive, on
  3.12/3.13, where `UP037` never fires); added the matching per-file-ignore to
  `template/pyproject.toml`, `profiles/library/pyproject.toml`, and
  `profiles/workspace/pyproject.toml` (the `service` profile has no override and inherits
  the template's). Also dropped a stray `# noqa: PLC0415` on `validate_contract.py`'s lazy
  `import yaml`, unused everywhere this vendors to (no consumer selects ruff's `PL` rules)
  and itself flagged by `RUF100` once `RUF` is enabled. Verified by rendering all three
  profiles at Python 3.12/3.13/3.14 and re-running the full test suite and
  `loop_self_evaluation.py`.

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
