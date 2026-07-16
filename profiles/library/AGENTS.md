# {{PROJECT_NAME}} engineering contract

## Project

- Runtime: Python {{PYTHON_VERSION}}
- Profile: library
- Package: `{{PACKAGE_NAME}}`
- Layout: `src/{{PACKAGE_NAME}}`
- Dependency manager: uv

Keep public APIs small, typed, documented, and backward compatible. Do not add a framework,
runtime container, or observability backend without a demonstrated consumer requirement.

Do not use `from __future__ import annotations`. Quote only the individual forward references that
require deferred evaluation.

## Quality gate

```bash
uv run python scripts/quality_gate.py
```

Use `--list` to discover named checks and `--check NAME` for focused work. Run the complete gate
before completion and distinguish regressions from pre-existing failures.

## Working method

1. Confirm behavior, compatibility constraints, and acceptance criteria.
2. Inspect affected public contracts, implementation, tests, and documentation.
3. Implement the smallest coherent change and add behavior-focused regression tests.
4. Run relevant named checks, then the complete gate.
5. Report verification evidence, assumptions, compatibility impact, and remaining risks.

Never read, write, log, commit, or transmit secrets. Keep dependencies minimal and reviewed. Use
MCP only for structured external access, keep mutations permission-gated, and validate its config
through the project quality gate.

When governance is enabled, run `uv run python scripts/governance_gate.py`, keep the records under
`governance/` current, and treat framework mappings as support statements rather than compliance or
certification claims. Evidence must remain metadata-only.
