# Codex Python Engineering Harness

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

## Generated project workflow

```bash
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
references used by this port.
