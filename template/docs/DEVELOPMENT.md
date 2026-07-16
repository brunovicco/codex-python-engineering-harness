# Development guide

## Setup

```bash
uv sync --frozen --all-groups
```

## Run checks

```bash
uv run python scripts/quality_gate.py
```

## Container

```bash
docker build -t {{PROJECT_NAME}} .
docker run --rm {{PROJECT_NAME}}
```

`Dockerfile` is a multi-stage, uv-based build: a `builder` stage installs the locked
dependencies and builds the package, then only the resulting virtualenv and source are copied
into a slim, non-root runtime image. The shipped `CMD` is a placeholder — this harness is
framework-agnostic and does not assume an ASGI app, CLI, or worker loop. Replace it with the
project's real entrypoint. Adjust `.dockerignore` if new top-level files or directories need to
be excluded from the build context.

## Local configuration

Copy `.env.example` only when the application supports local dotenv loading. Never commit `.env` or real credentials.

## Codex

- Run `/status` to inspect the active project and configuration.
- Run `/hooks` to inspect configured hooks.
- Run `codex --version` from the shell for an installation check.
- Use `$plan-change` before complex work.
- Use `$quality-gate` before completion.
- Use `$prepare-pr` to produce a reviewable PR description.

Codex discovers durable project guidance in `AGENTS.md`, workflows in `.agents/skills/`, and
trusted project configuration and hooks under `.codex/`. Skills do not silently delegate work;
the active agent follows their checked-in workflow and the user's requested scope.
