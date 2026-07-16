# Codex Python engineering harness

## Purpose

This repository owns a Codex-native bootstrap for Python projects. Keep the harness itself
separate from files distributed by `template/` and `profiles/`. The default template is a
single-package service; `service`, `library`, and `workspace` are generation profiles, not
packages in this repository.

## Commands

```bash
uv sync --all-groups
uv run ruff check --config pyproject.toml bootstrap.py tests template/scripts template/.codex/hooks plugins/python-engineering-harness/scripts scripts
uv run ruff format --config pyproject.toml --check bootstrap.py tests template/scripts template/.codex/hooks plugins/python-engineering-harness/scripts scripts
uv run mypy bootstrap.py tests template/scripts template/.codex/hooks
uv run python -m unittest discover -s tests -v
uv run python scripts/quality_gate.py
```

Generate a disposable profile with `python bootstrap.py --name sample --package sample --target
/tmp/sample --profile service`. Replace `service` with `library` or `workspace` as needed.

## Engineering rules

- Do not use `from __future__ import annotations` in any file. Quote only the individual forward
  references that require deferred evaluation.
- Preserve the source project; never read from it as a runtime dependency.
- Keep generated projects portable: no secrets, personal settings, machine-specific absolute
  paths, or required external credentials.
- Use `AGENTS.md` for persistent instructions, `.agents/skills/` for project skills,
  `.codex/config.toml` for project config, and one `.codex/hooks.json` per project layer.
- Keep plugin components at the plugin root and only `plugin.json` under `.codex-plugin/`.
- Plugin hook commands must resolve scripts through `PLUGIN_ROOT`.
- Do not add `.codex/rules/*.rules` for prose conventions. Codex rules are command execution
  policies; add them only for a concrete command-policy need and document their compatibility.
- Do not commit, push, publish, install the plugin, or mutate an external system unless requested.

## Definition of done

Run unit tests, lint, format, typecheck, the repository quality gate, architecture validation,
plugin validation, global forbidden-import and legacy-reference searches, and render/check all
three profiles from both their root and a relevant subdirectory.
