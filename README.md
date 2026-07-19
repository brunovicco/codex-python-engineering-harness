# Codex Python Engineering Harness

[![CI](https://github.com/brunovicco/codex-python-engineering-harness/actions/workflows/harness-quality.yml/badge.svg)](https://github.com/brunovicco/codex-python-engineering-harness/actions/workflows/harness-quality.yml)
[![Python 3.12-3.14](https://img.shields.io/badge/Python-3.12--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Codex-native, profile-driven bootstrap for production-oriented Python repositories. It creates
standalone service, library, or virtual-workspace projects with durable Codex instructions,
project configuration, skills, lifecycle hooks, architecture checks, MCP governance, and a single
quality gate.

## Quick start

```bash
python bootstrap.py \
  --name payments-api \
  --package payments_api \
  --target ../payments-api \
  --profile service \
  --git-init \
  --lock
```

Profiles:

- `service`: deployable `src/` package, container files, logging and tracing boundaries.
- `library`: reusable typed package without service/container assumptions.
- `workspace`: virtual uv workspace root; it creates no artificial package or member.

| Profile | Choose it for | Package created | Container and runtime boundaries |
|---|---|---:|---:|
| `service` | APIs, workers, agents, and deployable processes | Yes | Yes |
| `library` | Reusable typed Python packages | Yes | No |
| `workspace` | A multi-package repository whose members will be added later | No | No |

The bootstrap also supports `--dry-run`, non-destructive `--merge`, and `--check`. Run
`python bootstrap.py --help` for the complete interface.

Governance is an independent generator dimension and remains disabled by default for backward
compatibility. Enable a capability profile and repeat overlays as needed:

```bash
python bootstrap.py \
  --name payments-agent \
  --package payments_agent \
  --target ../payments-agent \
  --profile service \
  --governance-profile agentic \
  --governance-overlay dora \
  --governance-overlay iso-iec-42001
```

Governance profiles are `none`, `baseline`, `ai-assisted`, and `agentic`. Available overlays are
`dora`, `iso-iec-42001`, and `nist-sp-800-53`. Framework mappings describe control support and do
not claim organizational compliance or certification.

## Five-minute evaluation

Requirements: Python 3.12 or newer and `uv`.

```bash
target="$(mktemp -d)/harness-evaluation"
python bootstrap.py --name evaluation --package evaluation --target "$target" --profile service
cd "$target"
uv sync --all-groups --extra observability
uv run python scripts/quality_gate.py
```

Then inspect `AGENTS.md`, `.codex/config.toml`, `.codex/hooks.json`, `.agents/skills/`, and
`docs/ARCHITECTURE.md`. This evaluation creates only a disposable local project and requires no
credentials. Use the harness when you want an opinionated, repository-owned engineering baseline;
do not use it when an existing project cannot adopt its uv workflow or architectural constraints.

## Generated project workflow

```bash
uv lock --check
uv sync --frozen --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest
uv run python scripts/quality_gate.py
python /path/to/harness/bootstrap.py --target . --check
```

Trust the repository before expecting `.codex/config.toml` and `.codex/hooks.json` to load. Use
`/hooks` in Codex to review and trust new or changed hooks. Generated projects need no personal
Codex configuration and no credentials to build or test.

## Repository layout

- `template/`: service-compatible base copied into generated projects.
- `profiles/`: overlays and exclusions for `service`, `library`, and `workspace`.
- `governance/`: canonical controls, capability profiles, regulatory overlays, and schemas.
- `plugins/python-engineering-harness/`: installable Codex plugin with reusable skills and hooks.
- `.agents/plugins/marketplace.json`: repository marketplace entry.
- `tests/`: bootstrap, hook, validator, and distribution regression tests.
- `docs/ARCHITECTURE.md`: porting decisions and source mapping.

## Plugin

Add this repository as a local marketplace with
`codex plugin marketplace add /absolute/path/to/codex-python-engineering-harness`, restart the
desktop app, then install **Python Engineering Harness**. The marketplace does not install or
authenticate anything automatically.

## Verification

```bash
uv sync --all-groups
uv run python scripts/quality_gate.py
```

See `VALIDATION.md` for the latest verification record and `SOURCES.md` for official OpenAI
references used by this port. See `docs/EVALUATION.md` for the reproducible evaluation guide and
acceptance criteria, `docs/VERSIONING.md` for artifact lifecycles, `docs/UPGRADING.md` for
non-destructive upgrades (também em português: `docs/UPGRADING.pt-BR.md`),
`docs/ENTERPRISE_ROLLOUT.md` for rollout guidance, `CHANGELOG.md` for release history, and
`SECURITY.md` for private vulnerability reporting. Community participation is covered by
`CONTRIBUTING.md`, `SUPPORT.md`, and `CODE_OF_CONDUCT.md`. Structural parity with the sibling
`claude-python-engineering-harness` is checked in CI by `scripts/parity_check.py` against
`parity-manifest.json`.
