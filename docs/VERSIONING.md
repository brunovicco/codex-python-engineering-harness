# Versioning model

This repository contains three independently versioned artifacts:

| Artifact | Current version source | Meaning |
|---|---|---|
| Harness generator | `bootstrap.py` (`HARNESS_VERSION`) | Version recorded in generated project metadata and used for upgrade and drift checks. |
| Development package | root `pyproject.toml` | Local tooling package for developing and validating this repository; it is not the generated project's version. |
| Codex plugin | `plugins/python-engineering-harness/.codex-plugin/plugin.json` | Installable plugin release containing reusable skills and hooks. |

Versions do not need to match. A generator release can change templates without changing the
plugin, and a plugin release can improve workflows without changing generated files. Each artifact
uses semantic versioning within its own lifecycle.

The generated project's version is separately owned by that project and starts at `0.1.0` by
default. Upgrading the harness must never overwrite that application or library version.

Release notes must identify which artifact changed. Compatibility-impacting changes to generated
files require a harness version change and upgrade instructions. Plugin-only changes require a
plugin version change. The root development package changes only when its packaging contract
changes.
