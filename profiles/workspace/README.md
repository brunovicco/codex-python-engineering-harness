# {{PROJECT_NAME}}

Python {{PYTHON_VERSION}} uv workspace with a virtual, non-package root.
Governance profile: `{{GOVERNANCE_PROFILE}}`.

Declare real members in `[tool.uv.workspace]`, then run:

```bash
uv sync --frozen --all-packages
uv run python scripts/quality_gate.py
```

No artificial root package, empty service tree, or runtime Dockerfile is generated.
