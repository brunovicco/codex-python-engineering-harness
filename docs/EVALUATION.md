# Evaluation guide

This guide makes the harness claims reproducible. It separates repository checks from checks run in
freshly generated projects and records the commands, expected artifacts, and acceptance criteria.
It expands the README's five-minute evaluation.

## Five-minute evaluation

From a clean checkout with Python, Git, and uv installed:

```bash
python bootstrap.py --name demo-service --package demo_service \
  --target ../demo-service --profile service --git-init --lock
cd ../demo-service
uv sync --frozen --all-groups
uv run python scripts/quality_gate.py
```

The generated project should contain:

```text
demo-service/
├── .agents/skills/       # invocable project skills
├── .codex/               # config.toml, hooks.json, and hook scripts
├── .github/workflows/    # CI invoking the project-owned quality gate
├── docs/                 # architecture, privacy, MCP, and observability guidance
├── scripts/              # deterministic quality and policy validators
├── src/demo_service/     # Clean Architecture package roots
├── tests/                # starter regression tests
├── .harness.json         # generation metadata and content hashes
├── AGENTS.md
├── Dockerfile
└── pyproject.toml
```

Trust the repository before expecting `.codex/config.toml` and `.codex/hooks.json` to load, and
review new hooks with `/hooks` in Codex. The evaluation needs no credentials.

## Profile comparison

| Capability | service | library | workspace |
|---|---|---|---|
| Installable root package | Yes | Yes | No |
| Runtime container | Yes | No | No |
| Strict Mypy and tests | Yes | Yes | Per member |
| Clean Architecture boundaries | Yes | Yes | Per configured root |
| Observability starter (OpenTelemetry) | Optional | No | Per member |
| Intended use | Deployable backend | Reusable package | Multi-package repository |

## Acceptance criteria

The repository is ready for release when all of the following are true at the release commit:

1. The repository-owned gate (`uv run python scripts/quality_gate.py`) passes, including
   regression tests, Ruff, format, Mypy, Bandit, pip-audit, and the governance gate.
2. Fresh `service`, `library`, and `workspace` projects render for every supported Python version.
3. Each generated project passes frozen dependency sync and its own `scripts/quality_gate.py`.
4. The service image builds and runs as a non-root user; non-service profiles emit no Dockerfile.
5. Merge, dry-run, check, conflict numbering, file-mode preservation, and symlink-confinement
   regressions pass.
6. Hook and MCP tests cover malformed input, secret scanning, sensitive paths, trust
   classification, and prohibited literal credentials.
7. `VALIDATION.md` records the date, Python version, release commit, commands, and observed
   results.

## Recording results

Do not update pass counts by hand without running the corresponding command. For a release,
capture:

```bash
git rev-parse HEAD
python3 --version
uv run python scripts/quality_gate.py
git diff --check
```

Then run the generated-profile matrix in CI or reproduce each supported profile and Python version
locally. Link the successful workflow run from `VALIDATION.md`; do not treat a previous run from a
different commit as evidence for the release.

Dependabot checks pinned GitHub Actions and container references that appear directly in workflow
and Docker files. The Python base-image digests in `bootstrap.py` are template data and require a
manual refresh for every supported Python minor. Review upstream release notes, verify each digest
with `docker buildx imagetools inspect`, and require the complete CI matrix before merging updates.
