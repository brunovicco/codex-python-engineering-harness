#!/usr/bin/env python3
"""Render, upgrade, or check the Python engineering harness."""

import argparse
import contextlib
import hashlib
import json
import keyword
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HARNESS_VERSION = "1.2.0"
DEFAULT_BRANCH = "main"
PROFILES = ("service", "library", "workspace")
GOVERNANCE_CATALOG_VERSION = "2026.1"
GOVERNANCE_PROFILES = ("none", "baseline", "ai-assisted", "agentic")
GOVERNANCE_OVERLAYS = ("dora", "iso-iec-42001", "nist-sp-800-53")
TOKENS = {
    "{{PROJECT_NAME}}": "project_name",
    "{{PACKAGE_NAME}}": "package_name",
    "{{PYTHON_VERSION}}": "python_version",
    "{{RUFF_TARGET_VERSION}}": "ruff_target_version",
    "{{PROFILE}}": "profile",
    "{{GOVERNANCE_PROFILE}}": "governance_profile",
}
SUPPORTED_PYTHON_MINORS = {12, 13, 14}

PROFILE_EXCLUDES: dict[str, tuple[str, ...]] = {
    "service": (),
    "library": (
        ".dockerignore",
        ".env.example",
        "Dockerfile",
        ".agents/skills/scaffold-use-case",
        "docs/LLM_OBSERVABILITY.md",
        "docs/adr",
        "src/{{PACKAGE_NAME}}/adapters",
        "src/{{PACKAGE_NAME}}/application",
        "src/{{PACKAGE_NAME}}/domain",
        "src/{{PACKAGE_NAME}}/entrypoints",
        "tests/unit/test_logging.py",
        "tests/unit/test_observability.py",
        "tests/unit/test_tracing.py",
    ),
    "workspace": (
        ".dockerignore",
        ".env.example",
        "Dockerfile",
        ".agents/skills/scaffold-use-case",
        "docs/LLM_OBSERVABILITY.md",
        "docs/adr",
        "src",
        "tests",
    ),
}


@dataclass(frozen=True, slots=True)
class RenderedFile:
    """One fully rendered destination."""

    data: bytes
    mode: int


@dataclass(frozen=True, slots=True)
class PlannedChange:
    """Describe how one rendered file relates to the target."""

    relative: Path
    rendered: RenderedFile
    status: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", help="Project name, e.g. payments-api")
    parser.add_argument("--package", help="Python package, e.g. payments_api")
    parser.add_argument("--target", required=True, type=Path, help="Target repository")
    parser.add_argument("--python", default="3.13", dest="python_version")
    parser.add_argument("--profile", choices=PROFILES, default="service")
    parser.add_argument(
        "--governance-profile",
        choices=GOVERNANCE_PROFILES,
        default="none",
        help="Select capability-based governance controls",
    )
    parser.add_argument(
        "--governance-overlay",
        action="append",
        choices=GOVERNANCE_OVERLAYS,
        default=[],
        help="Add a regulatory governance overlay; repeatable",
    )
    parser.add_argument(
        "--merge", action="store_true", help="Upgrade without replacing custom files"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show new, equal, updated, and conflicting files"
    )
    parser.add_argument("--check", action="store_true", help="Check an existing generated project")
    parser.add_argument("--git-init", action="store_true", help="Initialize Git on branch main")
    parser.add_argument("--lock", action="store_true", help="Run uv lock after rendering")
    args = parser.parse_args(argv)
    if not args.check and (not args.name or not args.package):
        parser.error("--name and --package are required unless --check is used")
    if args.check and any((args.dry_run, args.git_init, args.lock, args.merge)):
        parser.error("--check cannot be combined with --dry-run, --merge, --git-init, or --lock")
    if args.check and (args.governance_profile != "none" or args.governance_overlay):
        parser.error("--check reads governance selection from .harness.json")
    if args.governance_profile == "none" and args.governance_overlay:
        parser.error("--governance-overlay requires a non-none --governance-profile")
    if len(args.governance_overlay) != len(set(args.governance_overlay)):
        parser.error("--governance-overlay cannot contain duplicates")
    return args


def normalize_python_version(value: str) -> tuple[str, str]:
    """Validate a Python version and return its version and Ruff target."""
    parts = value.split(".")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError(f"Invalid Python version: {value!r}; expected MAJOR.MINOR")
    major, minor = (int(part) for part in parts)
    if major != 3 or minor not in SUPPORTED_PYTHON_MINORS:
        supported = ", ".join(f"3.{item}" for item in sorted(SUPPORTED_PYTHON_MINORS))
        raise ValueError(f"Unsupported Python version {value!r}; choose one of: {supported}")
    normalized = f"{major}.{minor}"
    if value != normalized:
        raise ValueError(f"Invalid Python version: {value!r}; use canonical form {normalized!r}")
    return normalized, f"py{major}{minor}"


def validate_package_name(value: str) -> None:
    """Validate a Python package identifier."""
    if not value.isidentifier() or keyword.iskeyword(value):
        raise ValueError(f"Invalid Python package name: {value!r}")


def validate_project_name(value: str) -> None:
    """Validate a project/distribution name before substituting it into files."""
    if (
        not value
        or value[0] in ".-"
        or not all(character.isalnum() or character in ".-_" for character in value)
    ):
        raise ValueError(
            f"Invalid project name: {value!r}; use letters, numbers, dots, hyphens, or underscores"
        )


def render_text(content: str, values: dict[str, str]) -> str:
    """Replace scaffold tokens in text content."""
    for token, key in TOKENS.items():
        if token in content:
            content = content.replace(token, values.get(key, token))
    return content


def destination_for(relative: Path, values: dict[str, str]) -> Path:
    """Render tokens embedded in a relative destination path."""
    return Path(*(render_text(part, values) for part in relative.parts))


def ensure_within_target(path: Path, target: Path) -> None:
    """Reject destinations that escape the target through traversal or symlinks."""
    try:
        path.resolve().relative_to(target.resolve())
    except ValueError as exc:
        raise ValueError(f"Rendered destination escapes target directory: {path}") from exc


def write_atomic(path: Path, data: bytes, *, mode: int) -> None:
    """Atomically replace a destination while preserving the template file mode."""
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
            temporary.write(data)
            temporary.flush()
            os.fchmod(temporary.fileno(), mode)
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def conflict_destination(destination: Path) -> Path:
    """Return a conflict path that never overwrites an earlier suggestion."""
    candidate = destination.with_name(destination.name + ".harness-new")
    counter = 2
    while candidate.exists() or candidate.is_symlink():
        candidate = destination.with_name(f"{destination.name}.harness-new.{counter}")
        counter += 1
    return candidate


def sha256(data: bytes) -> str:
    """Return a stable content digest."""
    return hashlib.sha256(data).hexdigest()


def _render_source(source: Path, values: dict[str, str]) -> RenderedFile:
    data = source.read_bytes()
    with contextlib.suppress(UnicodeDecodeError):
        data = render_text(data.decode("utf-8"), values).encode("utf-8")
    return RenderedFile(data=data, mode=stat.S_IMODE(source.stat().st_mode))


def load_json_object(path: Path) -> dict[str, Any]:
    """Load a JSON object or raise a contextual validation error."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid governance JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Governance document must contain an object: {path}")
    return value


def compose_governance_profile(root: Path, profile: str, overlays: list[str]) -> dict[str, Any]:
    """Compose one capability profile with additive regulatory overlays."""
    selected = load_json_object(root / "governance" / "profiles" / f"{profile}.json")
    required = selected.get("required_controls")
    frameworks = selected.get("framework_versions")
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        raise ValueError(f"Governance profile {profile!r} has invalid required_controls")
    if not isinstance(frameworks, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in frameworks.items()
    ):
        raise ValueError(f"Governance profile {profile!r} has invalid framework_versions")

    control_ids = list(required)
    framework_versions = dict(frameworks)
    for overlay in overlays:
        definition = load_json_object(root / "governance" / "overlays" / f"{overlay}.json")
        overlay_controls = definition.get("required_controls")
        overlay_frameworks = definition.get("framework_versions")
        if not isinstance(overlay_controls, list) or not all(
            isinstance(item, str) for item in overlay_controls
        ):
            raise ValueError(f"Governance overlay {overlay!r} has invalid required_controls")
        if not isinstance(overlay_frameworks, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in overlay_frameworks.items()
        ):
            raise ValueError(f"Governance overlay {overlay!r} has invalid framework_versions")
        for framework, version in overlay_frameworks.items():
            existing = framework_versions.get(framework)
            if existing is not None and existing != version:
                raise ValueError(
                    f"Conflicting versions for {framework!r}: {existing!r} and {version!r}"
                )
            framework_versions[framework] = version
        control_ids.extend(overlay_controls)

    return {
        "framework_versions": dict(sorted(framework_versions.items())),
        "name": profile,
        "overlays": overlays,
        "required_controls": list(dict.fromkeys(control_ids)),
        "version": selected.get("version"),
    }


def rendered_json(value: dict[str, Any]) -> RenderedFile:
    """Serialize deterministic generated governance JSON."""
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    return RenderedFile(data=data, mode=0o644)


def rendered_control_catalog(root: Path, profile: str) -> RenderedFile:
    """Render profile-valid assurance evidence without distributing inapplicable tests."""
    catalog = load_json_object(root / "governance" / "catalog" / "controls.json")
    if profile == "service":
        return rendered_json(catalog)
    controls = catalog.get("controls")
    if not isinstance(controls, list):
        raise ValueError("Governance control catalog has invalid controls")
    for control in controls:
        if isinstance(control, dict) and control.get("id") == "CPH-OBS-001":
            assurance = control.get("assurance")
            if not isinstance(assurance, dict):
                raise ValueError("CPH-OBS-001 has invalid assurance")
            assurance["checks"] = [
                ".github/workflows/quality.yml",
                "scripts/quality_gate.py",
            ]
    return rendered_json(catalog)


def _excluded(relative: Path, profile: str) -> bool:
    rendered = relative.as_posix()
    for prefix in PROFILE_EXCLUDES[profile]:
        if rendered == prefix or rendered.startswith(prefix + "/"):
            return True
    return False


def rendered_profile(
    root: Path,
    profile: str,
    values: dict[str, str],
    governance_profile: str,
    governance_overlays: list[str],
) -> dict[Path, RenderedFile]:
    """Compose technical and governance profile inputs into one standalone project."""
    files: dict[Path, RenderedFile] = {}
    base = root / "template"
    for source in sorted(base.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(base)
        if "__pycache__" in relative.parts or _excluded(relative, profile):
            continue
        if governance_profile == "none" and relative.parts[0] == "governance":
            continue
        files[destination_for(relative, values)] = _render_source(source, values)

    overlay = root / "profiles" / profile
    if overlay.exists():
        for source in sorted(overlay.rglob("*")):
            if not source.is_file() or "__pycache__" in source.parts:
                continue
            relative = destination_for(source.relative_to(overlay), values)
            files[relative] = _render_source(source, values)

    if governance_profile != "none":
        governance = root / "governance"
        files[Path("governance/control-catalog.json")] = rendered_control_catalog(root, profile)
        files[Path("governance/governance-profile.json")] = rendered_json(
            compose_governance_profile(root, governance_profile, governance_overlays)
        )
        for schema in sorted((governance / "schemas").glob("*.json")):
            files[Path("governance/schemas") / schema.name] = _render_source(schema, values)
    return files


def load_manifest(target: Path) -> dict[str, Any]:
    """Load harness metadata, returning an empty manifest when absent or invalid."""
    path = target / ".harness.json"
    if not path.is_file() or path.is_symlink():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def manifest_files(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Normalize file records from a manifest."""
    files = manifest.get("files", {})
    if not isinstance(files, dict):
        return {}
    return {
        key: value
        for key, value in files.items()
        if isinstance(key, str) and isinstance(value, dict)
    }


def plan_changes(
    rendered: dict[Path, RenderedFile], target: Path, previous: dict[str, dict[str, Any]]
) -> list[PlannedChange]:
    """Classify rendered files without mutating the target."""
    changes: list[PlannedChange] = []
    for relative, item in sorted(rendered.items(), key=lambda pair: pair[0].as_posix()):
        destination = target / relative
        ensure_within_target(destination, target)
        if not destination.exists() and not destination.is_symlink():
            status = "new"
        elif (
            not destination.is_symlink()
            and destination.is_file()
            and destination.read_bytes() == item.data
        ):
            status = "same"
        else:
            record = previous.get(relative.as_posix(), {})
            old_hash = record.get("sha256")
            actual_hash = (
                sha256(destination.read_bytes())
                if destination.is_file() and not destination.is_symlink()
                else None
            )
            status = "update" if old_hash and actual_hash == old_hash else "conflict"
        changes.append(PlannedChange(relative=relative, rendered=item, status=status))
    return changes


def copy_template(template: Path, target: Path, values: dict[str, str], merge: bool) -> list[Path]:
    """Backward-compatible copier used by integrations and focused tests."""
    rendered = {
        destination_for(path.relative_to(template), values): _render_source(path, values)
        for path in sorted(template.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }
    changes = plan_changes(rendered, target, {})
    conflicts: list[Path] = []
    for change in changes:
        destination = target / change.relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if change.status == "same":
            continue
        if change.status == "conflict" and merge:
            candidate = conflict_destination(destination)
            ensure_within_target(candidate, target)
            write_atomic(candidate, change.rendered.data, mode=change.rendered.mode)
            conflicts.append(candidate)
            continue
        write_atomic(destination, change.rendered.data, mode=change.rendered.mode)
    return conflicts


def source_state(root: Path) -> tuple[str | None, bool]:
    """Return the harness source commit and dirty flag when available."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return None, False
    return commit, dirty


def build_manifest(
    *,
    root: Path,
    profile: str,
    governance_profile: str,
    governance_overlays: list[str],
    python_version: str,
    changes: list[PlannedChange],
    previous: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Create metadata for files that the harness owns after this render."""
    commit, dirty = source_state(root)
    files: dict[str, dict[str, Any]] = {}
    for change in changes:
        key = change.relative.as_posix()
        if change.status == "conflict":
            if key in previous:
                files[key] = previous[key]
            continue
        files[key] = {
            "sha256": sha256(change.rendered.data),
            "mode": f"{change.rendered.mode:04o}",
        }
    return {
        "version": HARNESS_VERSION,
        "profile": profile,
        "governanceProfile": governance_profile,
        "governanceOverlays": governance_overlays,
        "governanceCatalogVersion": GOVERNANCE_CATALOG_VERSION,
        "python": python_version,
        "sourceCommit": commit,
        "sourceDirty": dirty,
        "gitBranch": DEFAULT_BRANCH,
        "files": files,
    }


def apply_changes(changes: list[PlannedChange], target: Path, *, merge: bool) -> list[Path]:
    """Apply a render plan, preserving customized destinations as conflicts."""
    conflicts: list[Path] = []
    for change in changes:
        destination = target / change.relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if change.status == "same":
            continue
        if change.status == "conflict" and merge:
            candidate = conflict_destination(destination)
            ensure_within_target(candidate, target)
            write_atomic(candidate, change.rendered.data, mode=change.rendered.mode)
            conflicts.append(candidate)
            continue
        write_atomic(destination, change.rendered.data, mode=change.rendered.mode)
    return conflicts


def run_checked(command: list[str], cwd: Path) -> None:
    """Run a controlled bootstrap command and fail on errors."""
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)  # noqa: S603 -- controlled argv.


def _workflow_branches(workflow: Path) -> set[str]:
    if not workflow.is_file():
        return set()
    text = workflow.read_text(encoding="utf-8")
    match = re.search(r"branches:\s*\[([^]]+)]", text)
    if not match:
        return set()
    return {item.strip().strip("'\"") for item in match.group(1).split(",")}


def _current_branch(target: Path) -> str | None:
    if not (target / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=target,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or None


def _default_branch(target: Path, recorded: str | None) -> str | None:
    """Infer the repository default without treating a feature branch as configuration drift."""
    if not (target / ".git").exists():
        return recorded
    remote = subprocess.run(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        cwd=target,
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if remote.startswith("origin/"):
        return remote.removeprefix("origin/")
    branches = subprocess.run(
        ["git", "branch", "--format=%(refname:short)"],
        cwd=target,
        check=False,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    if len(branches) == 1:
        return branches[0].strip()
    if not branches:
        return _current_branch(target) or recorded
    return recorded


def check_target(target: Path) -> list[str]:
    """Return deterministic consistency errors for a generated project."""
    errors: list[str] = []
    manifest = load_manifest(target)
    if not manifest:
        return [".harness.json is missing or invalid"]
    if manifest.get("version") != HARNESS_VERSION:
        errors.append(
            f"harness version is {manifest.get('version')!r}; expected {HARNESS_VERSION!r}"
        )
    if manifest.get("profile") not in PROFILES:
        errors.append(f"unknown harness profile: {manifest.get('profile')!r}")
    governance_profile = manifest.get("governanceProfile")
    governance_overlays = manifest.get("governanceOverlays")
    if governance_profile not in GOVERNANCE_PROFILES:
        errors.append(f"unknown governance profile: {governance_profile!r}")
    if not isinstance(governance_overlays, list) or not all(
        isinstance(item, str) and item in GOVERNANCE_OVERLAYS for item in governance_overlays
    ):
        errors.append(f"invalid governance overlays: {governance_overlays!r}")
    elif len(governance_overlays) != len(set(governance_overlays)):
        errors.append("duplicate governance overlays")
    if governance_profile == "none" and governance_overlays:
        errors.append("governance overlays require an enabled governance profile")
    if manifest.get("governanceCatalogVersion") != GOVERNANCE_CATALOG_VERSION:
        errors.append(
            "governance catalog version is "
            f"{manifest.get('governanceCatalogVersion')!r}; "
            f"expected {GOVERNANCE_CATALOG_VERSION!r}"
        )
    if governance_profile in GOVERNANCE_PROFILES and governance_profile != "none":
        governance_manifest = target / "governance" / "governance-profile.json"
        if not governance_manifest.is_file() or governance_manifest.is_symlink():
            errors.append("enabled governance profile is missing governance-profile.json")

    for relative, record in sorted(manifest_files(manifest).items()):
        path = target / relative
        try:
            ensure_within_target(path, target)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not path.is_file() or path.is_symlink():
            errors.append(f"generated file missing or unsafe: {relative}")
            continue
        expected_mode = record.get("mode")
        actual_mode = f"{stat.S_IMODE(path.stat().st_mode):04o}"
        if expected_mode and actual_mode != expected_mode:
            errors.append(
                f"permission drift: {relative} is {actual_mode}, expected {expected_mode}"
            )
        expected_hash = record.get("sha256")
        if expected_hash and sha256(path.read_bytes()) != expected_hash:
            errors.append(f"generated file customized: {relative}")

    for path in sorted(target.rglob("*")):
        if ".git" in path.parts or ".venv" in path.parts or not path.is_file():
            continue
        if ".harness-new" in path.name:
            errors.append(f"pending conflict file: {path.relative_to(target)}")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        unresolved = sorted(token for token in TOKENS if token in content)
        if unresolved:
            errors.append(
                f"unrendered token in {path.relative_to(target)}: {', '.join(unresolved)}"
            )

    workflow = target / ".github" / "workflows" / "quality.yml"
    branch = _default_branch(target, manifest.get("gitBranch"))
    branches = _workflow_branches(workflow)
    if branch and branch not in branches:
        errors.append(
            f"CI branch mismatch: Git uses {branch!r}, workflow monitors {sorted(branches)!r}"
        )

    agents = target / "AGENTS.md"
    if agents.is_file():
        for referenced in sorted(
            set(
                re.findall(
                    r"(?:python\s+)?((?:\.?[\w-]+/)+[\w.-]+\.py)",
                    agents.read_text(encoding="utf-8"),
                )
            )
        ):
            if not (target / referenced).is_file():
                errors.append(f"documented command references missing file: {referenced}")
    return errors


def main(argv: list[str] | None = None) -> int:
    """Render the harness and run optional initialization steps."""
    args = parse_args(argv)
    target = args.target.resolve()
    if args.check:
        errors = check_target(target)
        if errors:
            print("Harness check failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        print(f"Harness {HARNESS_VERSION} check passed for {target}")
        return 0

    validate_project_name(args.name)
    validate_package_name(args.package)
    python_version, ruff_target_version = normalize_python_version(args.python_version)
    root = Path(__file__).resolve().parent
    values = {
        "project_name": args.name,
        "package_name": args.package,
        "python_version": python_version,
        "ruff_target_version": ruff_target_version,
        "profile": args.profile,
        "governance_profile": args.governance_profile,
    }

    if target.exists() and any(target.iterdir()) and not args.merge and not args.dry_run:
        print(
            f"Target is not empty: {target}. Use --merge to preserve existing files.",
            file=sys.stderr,
        )
        return 2

    previous_manifest = load_manifest(target)
    previous_files = manifest_files(previous_manifest)
    rendered = rendered_profile(
        root,
        args.profile,
        values,
        args.governance_profile,
        args.governance_overlay,
    )
    changes = plan_changes(rendered, target, previous_files)
    manifest = build_manifest(
        root=root,
        profile=args.profile,
        governance_profile=args.governance_profile,
        governance_overlays=args.governance_overlay,
        python_version=python_version,
        changes=changes,
        previous=previous_files,
    )

    if args.dry_run:
        for change in changes:
            print(f"{change.status.upper():8} {change.relative}")
        manifest_status = "SAME" if load_manifest(target) == manifest else "UPDATE"
        if not (target / ".harness.json").exists():
            manifest_status = "NEW"
        print(f"{manifest_status:8} .harness.json")
        return 1 if any(change.status == "conflict" for change in changes) else 0

    target.mkdir(parents=True, exist_ok=True)
    conflicts = apply_changes(changes, target, merge=args.merge)
    manifest_data = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    write_atomic(target / ".harness.json", manifest_data, mode=0o644)

    if args.git_init and not (target / ".git").exists():
        run_checked(["git", "init", "-b", DEFAULT_BRANCH], target)

    if args.lock:
        if shutil.which("uv") is None:
            print("uv was not found. Run `uv lock` after installing it.", file=sys.stderr)
        else:
            run_checked(["uv", "lock"], target)

    governance_label = args.governance_profile
    if args.governance_overlay:
        governance_label += f" + {', '.join(args.governance_overlay)}"
    print(
        f"Harness {HARNESS_VERSION} ({args.profile}; governance: {governance_label}) "
        f"rendered in {target}"
    )
    if conflicts:
        print("Review generated conflict files:")
        for conflict in conflicts:
            print(f"  - {conflict.relative_to(target)}")
    print(
        "Next: review AGENTS.md, .codex/config.toml, .codex/hooks.json, docs/MCP.md, "
        "and governance/ when enabled"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
