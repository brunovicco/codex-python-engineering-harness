#!/usr/bin/env python3
"""Report-only self-evaluation: render every profile, gate it, report the results.

Part of the Phase 0-1 Evidence-Gated Engineering Loop foundation
(docs/LOOPS.md). This script never modifies repository code: it renders
projects into a temporary directory that is discarded afterward, and its
only durable output is a JSON + Markdown report written to --output-dir.

Usage:
    uv run python scripts/loop_self_evaluation.py --output-dir build/loop-self-evaluation

Exit code reflects whether every rendered project's quality gate and the
manifest/plugin/documentation consistency check passed, so CI can decide
whether to flag the run without this script itself taking any action.
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ("service", "library", "workspace")
GOVERNANCE_CASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("none", ()),
    ("agentic", ("dora", "iso-iec-42001", "nist-sp-800-53")),
)


@dataclass
class GateRun:
    """One executed command's outcome, for the report."""

    label: str
    command: str
    passed: bool
    duration_s: float
    detail: str = ""


@dataclass
class Report:
    """The complete self-evaluation report."""

    generated_at: str
    harness_repository: str = "codex-python-engineering-harness"
    manifest_and_docs_consistency: GateRun | None = None
    projects: list[GateRun] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        """Return whether every recorded run passed."""
        runs = list(self.projects)
        if self.manifest_and_docs_consistency is not None:
            runs.append(self.manifest_and_docs_consistency)
        return all(run.passed for run in runs)


def run_command(label: str, command: list[str], cwd: Path) -> GateRun:
    """Run one command and record its pass/fail and duration."""
    started = time.monotonic()
    result = subprocess.run(  # noqa: S603 -- fixed argv, no shell.
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    duration = time.monotonic() - started
    detail = "" if result.returncode == 0 else (result.stdout + result.stderr)[-4000:]
    return GateRun(
        label=label,
        command=" ".join(command),
        passed=result.returncode == 0,
        duration_s=round(duration, 2),
        detail=detail,
    )


def evaluate_manifests_and_docs() -> GateRun:
    """Delegate manifest/plugin/documentation consistency to the existing test suite."""
    return run_command(
        "manifest-plugin-docs-consistency",
        [sys.executable, "-m", "unittest", "tests.test_harness.DistributionTests", "-v"],
        cwd=ROOT,
    )


def render_and_gate_project(
    temp_root: Path, profile: str, governance_profile: str, governance_overlays: tuple[str, ...]
) -> GateRun:
    """Render one profile/governance combination and run its quality gate."""
    label = f"{profile}-{governance_profile}"
    target = temp_root / label
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
        "--lock",
    ]
    for overlay in governance_overlays:
        render.extend(("--governance-overlay", overlay))

    render_result = run_command(f"render:{label}", render, cwd=ROOT)
    if not render_result.passed:
        return render_result

    sync = ["uv", "sync", "--frozen", "--all-groups"]
    if profile == "service":
        sync.append("--extra")
        sync.append("observability")
    sync_result = run_command(f"sync:{label}", sync, cwd=target)
    if not sync_result.passed:
        return sync_result

    return run_command(
        f"quality-gate:{label}", ["uv", "run", "python", "scripts/quality_gate.py"], cwd=target
    )


def build_report() -> Report:
    """Render every profile/governance combination and gate each one."""
    from datetime import UTC, datetime

    report = Report(generated_at=datetime.now(UTC).isoformat(timespec="seconds"))
    report.manifest_and_docs_consistency = evaluate_manifests_and_docs()

    with tempfile.TemporaryDirectory() as directory:
        temp_root = Path(directory)
        for profile in PROFILES:
            for governance_profile, governance_overlays in GOVERNANCE_CASES:
                report.projects.append(
                    render_and_gate_project(
                        temp_root, profile, governance_profile, governance_overlays
                    )
                )
    return report


def write_report(report: Report, output_dir: Path) -> None:
    """Write report.json and report.md into output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = asdict(report)
    (output_dir / "report.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Harness self-evaluation report",
        "",
        f"Generated: {report.generated_at}",
        f"Overall: {'PASS' if report.all_passed else 'FAIL'}",
        "",
        "This is a report-only workflow: nothing here modifies repository code.",
        "",
        "| Check | Passed | Duration (s) |",
        "| --- | --- | --- |",
    ]
    all_runs = list(report.projects)
    if report.manifest_and_docs_consistency is not None:
        all_runs = [report.manifest_and_docs_consistency, *all_runs]
    for run in all_runs:
        mark = "yes" if run.passed else "no"
        lines.append(f"| {run.label} | {mark} | {run.duration_s} |")

    failures = [run for run in all_runs if not run.passed]
    if failures:
        lines.append("")
        lines.append("## Divergences")
        for run in failures:
            lines.append("")
            lines.append(f"### {run.label}")
            lines.append(f"`{run.command}`")
            lines.append("")
            lines.append("```")
            lines.append(run.detail or "(no output captured)")
            lines.append("```")

    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse the --output-dir argument."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "build" / "loop-self-evaluation",
        help="Directory to write report.json and report.md into.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the self-evaluation and write its report."""
    args = parse_args()
    report = build_report()
    write_report(report, args.output_dir)
    print(f"Report written to {args.output_dir}")
    return 0 if report.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
