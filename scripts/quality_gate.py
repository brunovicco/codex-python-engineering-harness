#!/usr/bin/env python3
"""Run repository-owned checks, generated-profile checks, and plugin validation."""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], cwd: Path = ROOT) -> bool:
    """Run one check and return whether it passed."""
    print(f"\n==> {' '.join(command)}", flush=True)
    return subprocess.run(command, cwd=cwd, check=False).returncode == 0  # noqa: S603


def main() -> int:
    """Run deterministic repository checks and all generated profiles."""
    commands = [
        ["uv", "lock", "--check"],
        [
            "ruff",
            "check",
            "--config",
            "pyproject.toml",
            "bootstrap.py",
            "tests",
            "template/scripts",
            "template/.codex/hooks",
            "plugins/python-engineering-harness/scripts",
            "scripts",
        ],
        [
            "ruff",
            "format",
            "--config",
            "pyproject.toml",
            "--check",
            "bootstrap.py",
            "tests",
            "template/scripts",
            "template/.codex/hooks",
            "plugins/python-engineering-harness/scripts",
            "scripts",
        ],
        [
            "mypy",
            "bootstrap.py",
            "tests",
            "template/scripts",
            "template/.codex/hooks",
        ],
        [
            "bandit",
            "-ll",
            "-c",
            "pyproject.toml",
            "-r",
            "bootstrap.py",
            "template/scripts",
            "template/.codex/hooks",
            "plugins/python-engineering-harness/scripts",
            "scripts",
        ],
        ["pip-audit"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        [
            sys.executable,
            "template/scripts/governance_gate.py",
            "--source-root",
            ".",
            "--output",
            "build/governance-evidence/source-governance-report.json",
        ],
    ]
    failures = [" ".join(command) for command in commands if not run(command)]

    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        governance_cases = (
            ("none", ()),
            ("agentic", ("dora", "iso-iec-42001", "nist-sp-800-53")),
        )
        for profile in ("service", "library", "workspace"):
            for governance_profile, governance_overlays in governance_cases:
                label = f"{profile}-{governance_profile}"
                target = temporary / label
                render = [
                    sys.executable,
                    str(ROOT / "bootstrap.py"),
                    "--name",
                    f"sample-{label}",
                    "--package",
                    f"sample_{profile}_{governance_profile.replace('-', '_')}",
                    "--target",
                    str(target),
                    "--profile",
                    profile,
                    "--governance-profile",
                    governance_profile,
                ]
                for governance_overlay in governance_overlays:
                    render.extend(("--governance-overlay", governance_overlay))
                if not run(render):
                    failures.append(f"render {label}")
                    continue
                if not run(
                    [
                        sys.executable,
                        str(ROOT / "bootstrap.py"),
                        "--target",
                        str(target),
                        "--check",
                    ]
                ):
                    failures.append(f"check {label}")
                validators = (
                    "validate_architecture.py",
                    "validate_mcp_config.py",
                    "governance_gate.py",
                )
                for validator in validators:
                    if not run([sys.executable, f"scripts/{validator}"], cwd=target):
                        failures.append(f"{validator} {label}")
                if profile == "service" and governance_profile == "none":
                    if not run(
                        ["uv", "sync", "--all-groups", "--extra", "observability"], cwd=target
                    ):
                        failures.append(f"observability dependency sync {label}")
                    elif not run(["uv", "run", "python", "scripts/quality_gate.py"], cwd=target):
                        failures.append(f"generated project quality gate {label}")
                subdirectory = target / ("src" if profile != "workspace" else "docs")
                if not run(
                    [
                        sys.executable,
                        str(ROOT / "bootstrap.py"),
                        "--target",
                        str(target),
                        "--check",
                    ],
                    cwd=subdirectory,
                ):
                    failures.append(f"subdirectory check {label}")

    if failures:
        print("\nQuality gate failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("\nRepository quality gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
