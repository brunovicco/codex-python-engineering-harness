# Workspace development

```bash
uv sync --frozen --all-packages
uv run python scripts/quality_gate.py
```

Add real workspace members to `pyproject.toml`, along with their source and test root patterns. Use
`codex --version` for installation and configuration diagnostics.

Commands run in Codex's `workspace-write` sandbox with network access disabled and
`approval_policy = "on-request"` (`.codex/config.toml`). The sandbox does not restrict reads; the
hooks keep commands away from secrets.
