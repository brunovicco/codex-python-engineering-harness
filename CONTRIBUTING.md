# Contributing

This repository distributes generated project files from `template/` and `profiles/` and an
installable plugin from `plugins/python-engineering-harness/`. Keep duplicated behavior synchronized
across those outputs.

Before contributing, read `SUPPORT.md` and `CODE_OF_CONDUCT.md`. Use the issue forms for bugs and
feature proposals. Report suspected vulnerabilities privately as described in `SECURITY.md`.

## Local checks

Run the repository-owned gate:

```bash
uv sync --all-groups
uv run python scripts/quality_gate.py
```

For focused iteration, the individual commands are documented in `AGENTS.md`. The definition of
done also requires architecture and plugin validation, forbidden-import and legacy-reference
searches, and rendering all three profiles from their root and a relevant subdirectory.

Do not use `from __future__ import annotations`. Quote only an individual forward reference when
evaluation order requires it.

## Source ownership

- `template/`: service-compatible canonical generated files.
- `profiles/library/` and `profiles/workspace/`: profile overlays and exclusions.
- `template/.codex/hooks/` and plugin `scripts/`: synchronized safety behavior.
- `template/.agents/skills/` and plugin `skills/`: project and reusable workflow variants.
- `template/scripts/`: deterministic project validators and quality gate.
- `governance/`: canonical controls, profiles, overlays, and schemas.

Prefer changing the canonical template first, then port the equivalent plugin or profile change.
Regression tests verify duplicated security scripts remain identical.

## Pull requests

- Keep changes focused and link the relevant issue when one exists.
- Add tests for behavior changes and list the exact validation commands executed.
- Consider service, library, and workspace behavior.
- Review security, privacy, secrets, permissions, MCP trust and data egress, and supply chain impact.
- Document compatibility and migration impact in `docs/UPGRADING.md` when applicable.
- Update `CHANGELOG.md` for notable unreleased changes.
- Update `VALIDATION.md` only with evidence actually produced for an identified source commit.
- Do not weaken a deterministic quality or security control merely to make validation pass.

Submission and review are governed by `CODE_OF_CONDUCT.md`; support expectations and feature
selection criteria are defined in `SUPPORT.md`.
