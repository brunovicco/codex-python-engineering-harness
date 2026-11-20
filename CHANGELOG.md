# Changelog

All notable changes to the harness are documented here. Harness, development package, and plugin
versions are independent; see `docs/VERSIONING.md`.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the harness uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security

- Re-vendored the loop-contract validator from `engineering-loop-schemas` v0.3.0
  (`5340d491b46f4fabc967c81bb3e5204104b6b5d8`). The previously vendored v0.1.2 validator accepted
  contracts with unknown properties, arbitrary `version` values, and report-only contracts with
  `human_review.required: false`; v0.3.0 enforces the canonical JSON Schema and rejects all three.
  Valid existing contracts remain valid (contract wire format stays `1.0.0`).
- `validate_loop_schema_vendor.py` now verifies manifest format `2.0.0`: the size and SHA-256 of
  every Python source and of the four canonical JSON Schemas, every declared import adaptation,
  and the absence of any file the manifest does not declare (for example a planted module).
- Refreshed vulnerable development-only transitive dependencies in `uv.lock`, which made the
  repository `pip-audit` check (and therefore the `repository-quality` job on `main`) fail:
  `certifi` 2026.10.23, `filelock` 4.2.12, `msgpack` 1.2.4, `pip` 26.3, and `urllib3` 2.8.0. All
  are pulled in by `pip-audit`; no runtime dependency of generated projects changes.
- Pinned `actions/checkout` to a full commit SHA in every distributed workflow (`template/` and
  `profiles/`), and updated the distributed `astral-sh/setup-uv` pin from v8.1.0 to v10.3.3.
  Generated projects previously received an outdated `setup-uv` and, where a tag was used, a
  mutable action reference.

### Changed

- **Generated-project change; harness generator 1.3.0.** The Evidence-Gated Engineering Loop layer
  (`scripts/_vendor_loop_schemas/`, `validate_loop_contracts.py`, `validate_loop_schema_vendor.py`
  and their quality-gate checks) is now opt-in through `bootstrap.py --loop` instead of being
  rendered into every project, where it was a no-op unless a human added a contract. The selection
  is recorded as `loop` in `.harness.json`; `--merge` keeps it, and a project rendered before this
  change that tracks the vendored bundle keeps the layer. `--no-loop` disables it and lists the
  files left in place. A contract under `.loop/contracts/` without the layer fails both the
  generated quality gate and `bootstrap.py --check`. See `docs/LOOPS.md` and `docs/UPGRADING.md`.
- The repository quality gate, the self-evaluation workflow, and the CI generated-profiles matrix
  render the loop layer (with the agentic governance profile, and on every profile and Python
  version, respectively), while the `none` case keeps covering the default render.
- Repository mypy treats the vendored bundle as third-party code (`ignore_errors` for
  `_vendor_loop_schemas.*`): mypy 2.4 reports redundant casts in it that belong upstream, and the
  bundle is integrity-verified and must not be edited locally.
- The isolated lint in the `test` job now reads the ruff version from `uv.lock` instead of a
  hard-coded `ruff==0.15.20`, so it can never drift from the version the repository quality gate
  uses, and Dependabot updates both together. Its rule set is pinned to `E4,E7,E9,F`, the set it
  enforced before: `--isolated` ignores project config, and ruff 0.17 expanded its default
  selection from 59 to 407 rules, which would otherwise change the check under every update.
- Updated the harness CI actions: `actions/checkout` v7.0.1, `actions/setup-python` v7.1.0,
  `astral-sh/setup-uv` v10.3.3, and `actions/upload-artifact` v7.0.2, all pinned to full commit
  SHAs verified against their release tags. The only inputs used (`python-version`, `version`)
  are unchanged across these major versions. Supersedes the open Dependabot pull requests.
- `.github/dependabot.yml` is now identical in shape across the sibling harnesses: weekly grouped
  updates for GitHub Actions in the repository *and* in the distributed `template/` and `profiles/`
  workflows, for the `uv` lockfile (the former `pip` ecosystem could not read `uv.lock`, so
  lockfile vulnerabilities never produced update PRs), and for the template container images.
- Added regression tests that require every workflow action, including distributed ones, to be
  pinned to a full commit SHA with a version comment, and that keep Dependabot pointed at every
  distributed workflow directory.

## [1.3.0] - 2026-07-20

### Added

- Documentation parity with the sibling `claude-python-engineering-harness`:
  `docs/EVALUATION.md` (reproducible evaluation guide and acceptance criteria),
  `docs/ENTERPRISE_ROLLOUT.md` (ownership, distribution, MCP rollout, and metrics), and pt-BR
  translations `docs/LOOPS.pt-BR.md`, `docs/UPGRADING.pt-BR.md`, and
  `docs/ENTERPRISE_ROLLOUT.pt-BR.md`, under the language policy now documented in
  `CONTRIBUTING.md`.
- `scripts/parity_check.py` with `parity-manifest.json` and `parity-exceptions.json`: a
  deterministic check, shared with the sibling `claude-python-engineering-harness`, that fails CI
  when a parity-required artifact is missing and is not declared as an intentional divergence.
  Wired into CI.
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
  - The shared validator is now consumed as the deterministic `engineering-loop-schemas v0.1.2`
    bundle pinned to `0459d61b7b1d4e7b46709e6d3895770553e6fab0`. Its `manifest.json` records
    source provenance, file sizes, SHA-256 hashes, and the declared package-import adaptation.
    The mandatory `loop-schema-vendor` quality check validates the bundle offline, and regression
    tests prove that manual tampering is rejected. The earlier `75a63eef...` integration described
    below was an intermediate pre-release state and is superseded by this published bundle.

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

[Unreleased]: https://github.com/brunovicco/codex-python-engineering-harness/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/brunovicco/codex-python-engineering-harness/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/brunovicco/codex-python-engineering-harness/releases/tag/v1.2.0
