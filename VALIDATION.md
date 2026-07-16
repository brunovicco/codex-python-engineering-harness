# Validation record

Validated on 2026-07-16 (America/Sao_Paulo) with Python 3.12 for the harness and Python 3.13 for
generated profiles.

## Results

- Repository quality gate: passed.
- Unit tests: 45 passed.
- Ruff lint and format: passed.
- Strict Mypy: passed.
- Bandit medium/high findings: none.
- `pip-audit`: no known vulnerabilities.
- Plugin creator validation: passed.
- Governance source catalog: passed; 11 controls, four capability profiles, and three overlays.
- Governance regression tests: profile composition, duplicate-overlay rejection, untreated high
  risk, expired exception, and evidence-path validation passed.
- Generated `service`: full gate passed; 12 tests; 96.67% coverage.
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
