# Validation record

## Current validation — Phase 0-1

Validated on 2026-07-18 for the report-only Evidence-Gated Engineering Loop foundation.

### Identity and provenance

- Published repository commit:
  `59b29429c4b50984e2ceffd9f411ef2028a72e8b`.
- Harness generator version: `1.2.1` (`bootstrap.py` `HARNESS_VERSION`).
- Shared schemas: `v0.1.2` at
  `0459d61b7b1d4e7b46709e6d3895770553e6fab0`.
- Final integration: pull request
  [#8](https://github.com/brunovicco/codex-python-engineering-harness/pull/8).
- The pull-request quality run validated source head
  `ed0f5bd6827bba8cfef7948bb339b694dbfb62d5` before GitHub recreated the commit through squash
  merge:
  <https://github.com/brunovicco/codex-python-engineering-harness/actions/runs/29660517744>.

### Results

- Repository quality gate: passed.
- Regression tests: 70 passed.
- Ruff lint and format check: passed.
- Strict Mypy: passed.
- Bandit medium/high findings: none.
- `pip-audit`: no known vulnerabilities.
- `loop-schema-vendor`: passed for `v0.1.2`.
- Positive bundle-integrity test: passed.
- Manual-tampering detection test: passed.
- Legacy provider-reference regression test: passed.
- Harness self-evaluation: `Overall: PASS`.
- Complete quality gates passed for all six profile/governance combinations:
  - `service-none`;
  - `service-agentic`;
  - `library-none`;
  - `library-agentic`;
  - `workspace-none`;
  - `workspace-agentic`.

### Scope and limitations

This validation covers Phase 0-1 only. The repository can validate contracts, execute existing
quality gates, verify vendored-schema integrity, render temporary profiles, and produce reports.
It does not provide a loop runner, state machine, evaluator runtime, autonomous candidate creation,
candidate promotion, merge, or deployment.

The builder's report remains non-authoritative. A quality gate is the technical authority, and
human review remains required before any promotion decision.

The self-evaluation workflow still uses the previously pinned `setup-uv` action while the main
quality workflow uses the newer approved pin. Aligning those pins is CI maintenance and should be
performed in a separate change from this documentation record.

### Reproduce the Phase 0-1 validation

```bash
uv lock --check
uv sync --frozen --all-groups
uv run python scripts/quality_gate.py
uv run python scripts/loop_self_evaluation.py \
  --output-dir build/loop-self-evaluation
git diff --check
```

## Previous validation — 2026-07-16

Validated on 2026-07-16 (America/Sao_Paulo) with Python 3.12 for the harness and Python 3.13 for
generated profiles.

- Validated source commit: `f134a853b17c15caf9774d18ab20141f06d81714`.
- Successful GitHub Actions run:
  <https://github.com/brunovicco/codex-python-engineering-harness/actions/runs/29540528684>.
- This record is stored in a later documentation-only release commit so it can identify the
  validated source without an impossible self-referential commit hash.

## Results

- Repository quality gate: passed.
- Unit tests: 48 passed.
- Ruff lint and format: passed.
- Strict Mypy: passed.
- Bandit medium/high findings: none.
- `pip-audit`: no known vulnerabilities.
- Plugin creator validation: passed.
- Governance source catalog: passed; 11 controls, four capability profiles, and three overlays.
- Governance regression tests: profile composition, duplicate-overlay rejection, untreated high
  risk, expired exception, and evidence-path validation passed.
- Generated `service`: full gate passed; 20 tests; 92.31% coverage.
- Generated `library`: full gate passed; 1 test; 100% coverage.
- Generated `workspace`: lock, lint, format, architecture, MCP, and dependency audit passed;
  package-root checks correctly skipped because the initial workspace has no artificial members.
- Generated `service`, `library`, and `workspace` with `agentic` governance plus DORA,
  ISO/IEC 42001, and NIST SP 800-53 overlays: governance gate and complete applicable project
  quality gates passed.
- Bootstrap `--check`: passed for every profile from the project root and a relevant subdirectory.
- Codex CLI loaded each generated project config from a relevant subdirectory and reported hooks
  as stable and enabled.
- Forbidden annotation import search across repository Python files: no matches.
- Legacy tool-reference regression test: passed.
- Changed-file high-confidence secret scan: passed.

## A1 follow-up: sensitive-file read protection (2026-07-18)

- Added `sensitive_patterns.py` as the single source of truth for denylisted paths, imported by
  `protect_sensitive_files.py`, `validate_bash.py`, and `guard_mcp.py`.
- Extended `validate_bash.py` and `guard_mcp.py` to deny the same sensitive-path patterns as
  `protect_sensitive_files.py` (previously Bash covered only a narrower ad hoc pattern and MCP
  covered none).
- Fixed the plugin's `hooks.json`, which never wired `protect_sensitive_files.py` into
  `PreToolUse` for `apply_patch`/`Edit`/`Write`.
- Added `SensitiveFileReadProtectionTests` (`tests/test_harness.py`): 5 sensitive patterns
  (`.env`, credentials directory, SSH key, AWS credentials, Terraform state) each denied across
  3 tool categories (Bash, apply_patch/Edit/Write, MCP), plus allow-list regression for ordinary
  files and a template/plugin parity check.
- Repository quality gate: passed (`uv run python scripts/quality_gate.py`).
- Unit tests: 59 passed, 81 subtests passed (`uv run python -m pytest tests/ -q`).
- Documented finding: Codex CLI (per
  <https://developers.openai.com/codex/hooks#tool-coverage>) has no native `Read`/`Grep`/`Glob`
  function tools distinct from Bash and MCP; file inspection happens through `Bash`/
  `exec_command`, `apply_patch` context, or MCP tools. Read protection is therefore achieved by
  hardening those three hook paths rather than adding matchers for tool names Codex does not
  expose.

## Reproduce

```bash
uv sync --all-groups
uv run python scripts/quality_gate.py
uv run python template/scripts/governance_gate.py --source-root .
python /path/to/plugin-creator/scripts/validate_plugin.py plugins/python-engineering-harness
rg -n 'from __future__ import annotations' . --glob '*.py'
uv run python -m unittest tests.test_harness.DistributionTests -v
```

The installed CLI does not accept `--strict-config` on the read-only `features` diagnostic
subcommand. Native loading was therefore checked with `codex features list`, while TOML/JSON
parsing and project structure are enforced by automated tests and validators.
