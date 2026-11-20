# Development guide

```bash
uv sync --frozen
uv run python scripts/quality_gate.py
```

Use `uv run python scripts/quality_gate.py --list` to discover focused checks. Use `codex --version`
for installation and configuration diagnostics.

Commands run in Codex's `workspace-write` sandbox with network access disabled and
`approval_policy = "on-request"` (`.codex/config.toml`). The sandbox does not restrict reads; the
hooks keep commands away from secrets.
