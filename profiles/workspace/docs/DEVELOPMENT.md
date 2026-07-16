# Workspace development

```bash
uv sync --frozen --all-packages
uv run python scripts/quality_gate.py
```

Add real workspace members to `pyproject.toml`, along with their source and test root patterns. Use
`codex --version` for installation and configuration diagnostics.
