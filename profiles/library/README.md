# {{PROJECT_NAME}}

Framework-neutral Python {{PYTHON_VERSION}} library using uv.
Governance profile: `{{GOVERNANCE_PROFILE}}`.

```bash
uv lock --check
uv sync --frozen
uv run python scripts/quality_gate.py
```

The profile intentionally has no runtime framework, Dockerfile, structured-logging dependency, or
external tracing backend. See `AGENTS.md` for the engineering contract.
