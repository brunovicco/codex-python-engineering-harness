#!/usr/bin/env python3
"""Validate governance selections, records, and source definitions deterministically."""

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

VALID_ASSURANCE_TYPES = {"automated", "inherited", "manual"}
VALID_CONTROL_STATUSES = {
    "implemented",
    "inherited",
    "not_applicable",
    "partially_implemented",
    "planned",
}
VALID_COVERAGE = {"full", "inherited", "not_applicable", "partial", "supports"}
VALID_RISK_DECISIONS = {"accept", "avoid", "mitigate", "transfer"}
VALID_RISK_SEVERITIES = {"critical", "high", "low", "medium"}


def read_object(path: Path) -> dict[str, Any]:
    """Read a JSON object with a stable, contextual error."""
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"missing or unsafe JSON document: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON document: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must contain an object: {path}")
    return value


def string_list(value: object) -> list[str] | None:
    """Return a list containing only strings, or None for invalid input."""
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return value


def string_map(value: object) -> dict[str, str] | None:
    """Return a string-to-string mapping, or None for invalid input."""
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    ):
        return None
    return value


def evidence_path(root: Path, relative: str, *, source_mode: bool) -> Path:
    """Resolve evidence from a generated project or the distributable template."""
    direct = root / relative
    if direct.exists() or not source_mode:
        return direct
    return root / "template" / relative


def validate_profile(profile: dict[str, Any], *, label: str) -> list[str]:
    """Validate one profile or overlay document."""
    errors: list[str] = []
    name = profile.get("name")
    if not isinstance(name, str) or not name:
        errors.append(f"{label}: name must be a non-empty string")
    version = profile.get("version")
    if not isinstance(version, str) or not version:
        errors.append(f"{label}: version must be a non-empty string")
    required = string_list(profile.get("required_controls"))
    if required is None:
        errors.append(f"{label}: required_controls must be a list of strings")
    elif len(required) != len(set(required)):
        errors.append(f"{label}: required_controls contains duplicates")
    frameworks = string_map(profile.get("framework_versions"))
    if frameworks is None or any(not value for value in (frameworks or {}).values()):
        errors.append(f"{label}: framework_versions must contain non-empty string versions")
    overlays = profile.get("overlays")
    if overlays is not None:
        overlay_names = string_list(overlays)
        if overlay_names is None or len(overlay_names) != len(set(overlay_names)):
            errors.append(f"{label}: overlays must be a unique list of strings")
    return errors


def validate_mapping(control_id: str, mapping: object) -> list[str]:
    """Validate one framework mapping without reproducing framework text."""
    if not isinstance(mapping, dict):
        return [f"{control_id}: mapping must be an object"]
    errors: list[str] = []
    for field in ("framework", "reference", "version"):
        if not isinstance(mapping.get(field), str) or not mapping[field]:
            errors.append(f"{control_id}: mapping {field} must be a non-empty string")
    if mapping.get("coverage") not in VALID_COVERAGE:
        errors.append(f"{control_id}: mapping coverage is invalid")
    return errors


def validate_control(
    control: object,
    *,
    root: Path,
    source_mode: bool,
) -> tuple[str | None, list[str]]:
    """Validate one canonical control and its referenced evidence checks."""
    if not isinstance(control, dict):
        return None, ["control catalog entry must be an object"]
    errors: list[str] = []
    control_id = control.get("id")
    if not isinstance(control_id, str) or not control_id:
        return None, ["control id must be a non-empty string"]
    for field in ("title", "description", "category"):
        if not isinstance(control.get(field), str) or not control[field]:
            errors.append(f"{control_id}: {field} must be a non-empty string")
    if control.get("status") not in VALID_CONTROL_STATUSES:
        errors.append(f"{control_id}: invalid control status")

    ownership = control.get("ownership")
    if not isinstance(ownership, dict):
        errors.append(f"{control_id}: ownership must be an object")
    else:
        for field in ("control_owner", "implementation_owner", "evidence_owner"):
            if not isinstance(ownership.get(field), str) or not ownership[field]:
                errors.append(f"{control_id}: missing ownership.{field}")

    assurance = control.get("assurance")
    if not isinstance(assurance, dict):
        errors.append(f"{control_id}: assurance must be an object")
    else:
        assurance_type = assurance.get("type")
        if assurance_type not in VALID_ASSURANCE_TYPES:
            errors.append(f"{control_id}: invalid assurance type")
        if not isinstance(assurance.get("frequency"), str) or not assurance["frequency"]:
            errors.append(f"{control_id}: assurance frequency is required")
        checks = string_list(assurance.get("checks"))
        if checks is None or not checks:
            errors.append(f"{control_id}: assurance checks must be a non-empty string list")
        else:
            for check in checks:
                if Path(check).is_absolute() or ".." in Path(check).parts:
                    errors.append(f"{control_id}: unsafe evidence check path: {check}")
                    continue
                path = evidence_path(root, check, source_mode=source_mode)
                if not path.is_file() or path.is_symlink():
                    errors.append(f"{control_id}: evidence check does not exist: {check}")

    mappings = control.get("mappings")
    if not isinstance(mappings, list) or not mappings:
        errors.append(f"{control_id}: mappings must be a non-empty list")
    else:
        for mapping in mappings:
            errors.extend(validate_mapping(control_id, mapping))
    return control_id, errors


def validate_catalog(
    catalog: dict[str, Any],
    *,
    root: Path,
    source_mode: bool,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Validate the canonical catalog and return controls keyed by id."""
    errors: list[str] = []
    if not isinstance(catalog.get("version"), str) or not catalog["version"]:
        errors.append("control catalog version must be a non-empty string")
    raw_controls = catalog.get("controls")
    if not isinstance(raw_controls, list):
        return {}, [*errors, "control catalog controls must be a list"]
    controls: dict[str, dict[str, Any]] = {}
    for control in raw_controls:
        control_id, control_errors = validate_control(
            control,
            root=root,
            source_mode=source_mode,
        )
        errors.extend(control_errors)
        if control_id is None or not isinstance(control, dict):
            continue
        if control_id in controls:
            errors.append(f"duplicate control id: {control_id}")
        controls[control_id] = control
    return controls, errors


def validate_selection(
    profile: dict[str, Any], controls: dict[str, dict[str, Any]], *, label: str
) -> list[str]:
    """Check that a selected profile references existing controls and pinned frameworks."""
    errors = validate_profile(profile, label=label)
    required = string_list(profile.get("required_controls")) or []
    for control_id in required:
        if control_id not in controls:
            errors.append(f"{label}: required control is missing from catalog: {control_id}")
    return errors


def validate_risks(root: Path) -> list[str]:
    """Require formal treatment for high and critical risks."""
    path = root / "governance" / "risks" / "risk-register.json"
    try:
        document = read_object(path)
    except ValueError as exc:
        return [str(exc)]
    risks = document.get("risks")
    if not isinstance(risks, list):
        return ["risk register risks must be a list"]
    errors: list[str] = []
    ids: set[str] = set()
    for index, risk in enumerate(risks):
        label = f"risk[{index}]"
        if not isinstance(risk, dict):
            errors.append(f"{label}: must be an object")
            continue
        risk_id = risk.get("id")
        if not isinstance(risk_id, str) or not risk_id:
            errors.append(f"{label}: id is required")
        elif risk_id in ids:
            errors.append(f"duplicate risk id: {risk_id}")
        else:
            ids.add(risk_id)
            label = risk_id
        severity = risk.get("severity")
        if severity not in VALID_RISK_SEVERITIES:
            errors.append(f"{label}: invalid severity")
        if not isinstance(risk.get("owner"), str) or not risk["owner"]:
            errors.append(f"{label}: owner is required")
        if severity in {"high", "critical"} and risk.get("decision") not in VALID_RISK_DECISIONS:
            errors.append(f"{label}: high or critical risk requires a formal decision")
    return errors


def validate_exceptions(root: Path, *, today: date) -> list[str]:
    """Reject malformed and expired approved exceptions."""
    path = root / "governance" / "exceptions.json"
    try:
        document = read_object(path)
    except ValueError as exc:
        return [str(exc)]
    exceptions = document.get("exceptions")
    if not isinstance(exceptions, list):
        return ["governance exceptions must be a list"]
    errors: list[str] = []
    ids: set[str] = set()
    for index, exception in enumerate(exceptions):
        label = f"exception[{index}]"
        if not isinstance(exception, dict):
            errors.append(f"{label}: must be an object")
            continue
        exception_id = exception.get("id")
        if not isinstance(exception_id, str) or not exception_id:
            errors.append(f"{label}: id is required")
        elif exception_id in ids:
            errors.append(f"duplicate exception id: {exception_id}")
        else:
            ids.add(exception_id)
            label = exception_id
        if not isinstance(exception.get("owner"), str) or not exception["owner"]:
            errors.append(f"{label}: owner is required")
        if exception.get("status") not in {"approved", "closed"}:
            errors.append(f"{label}: status must be approved or closed")
        expires_on = exception.get("expires_on")
        try:
            expires = date.fromisoformat(expires_on) if isinstance(expires_on, str) else None
        except ValueError:
            expires = None
        if expires is None:
            errors.append(f"{label}: expires_on must be an ISO date")
        elif exception.get("status") == "approved" and expires < today:
            errors.append(f"{label}: approved exception expired on {expires.isoformat()}")
    return errors


def report_for_selection(
    *,
    profile: dict[str, Any],
    catalog: dict[str, Any],
    controls: dict[str, dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    """Build stable machine-readable evidence for one selection."""
    required = string_list(profile.get("required_controls")) or []
    status_counts = Counter(
        str(controls[control_id].get("status")) for control_id in required if control_id in controls
    )
    return {
        "catalog_version": catalog.get("version"),
        "errors": errors,
        "framework_versions": profile.get("framework_versions", {}),
        "governance_profile": profile.get("name"),
        "overlays": profile.get("overlays", []),
        "required_controls": required,
        "status": "fail" if errors else "pass",
        "status_counts": dict(sorted(status_counts.items())),
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    """Write deterministic evidence without embedding repository content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_generated(root: Path, output: Path | None) -> tuple[dict[str, Any], list[str]]:
    """Validate one generated project's selected governance state."""
    governance = root / "governance"
    profile_path = governance / "governance-profile.json"
    if not profile_path.exists():
        report = {
            "errors": [],
            "governance_profile": "none",
            "overlays": [],
            "required_controls": [],
            "status": "pass",
            "status_counts": {},
        }
        if output is not None:
            write_report(output, report)
        return report, []
    try:
        profile = read_object(profile_path)
        catalog = read_object(governance / "control-catalog.json")
    except ValueError as exc:
        return {"errors": [str(exc)], "status": "fail"}, [str(exc)]
    controls, errors = validate_catalog(catalog, root=root, source_mode=False)
    errors.extend(validate_selection(profile, controls, label="selected profile"))
    errors.extend(validate_risks(root))
    errors.extend(validate_exceptions(root, today=date.today()))
    report = report_for_selection(
        profile=profile,
        catalog=catalog,
        controls=controls,
        errors=errors,
    )
    destination = output or root / "build/governance-evidence/governance-report.json"
    write_report(destination, report)
    return report, errors


def run_source(root: Path, output: Path | None) -> tuple[dict[str, Any], list[str]]:
    """Validate all canonical profiles and overlays owned by the harness."""
    governance = root / "governance"
    try:
        catalog = read_object(governance / "catalog" / "controls.json")
    except ValueError as exc:
        return {"errors": [str(exc)], "status": "fail"}, [str(exc)]
    controls, errors = validate_catalog(catalog, root=root, source_mode=True)
    selections: list[str] = []
    for kind in ("profiles", "overlays"):
        paths = sorted((governance / kind).glob("*.json"))
        if not paths:
            errors.append(f"no governance {kind} found")
        for path in paths:
            try:
                selection = read_object(path)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            label = f"{kind[:-1]} {path.stem}"
            errors.extend(validate_selection(selection, controls, label=label))
            if selection.get("name") != path.stem:
                errors.append(f"{label}: name must match file name")
            selections.append(f"{kind}/{path.name}")
    report = {
        "catalog_version": catalog.get("version"),
        "control_count": len(controls),
        "errors": errors,
        "selections": selections,
        "status": "fail" if errors else "pass",
    }
    if output is not None:
        write_report(output, report)
    return report, errors


def parse_args() -> argparse.Namespace:
    """Parse generated-project and source-catalog modes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Generated project root")
    parser.add_argument("--source-root", type=Path, help="Harness source root")
    parser.add_argument("--output", type=Path, help="Override the evidence report path")
    args = parser.parse_args()
    if args.root and args.source_root:
        parser.error("--root and --source-root are mutually exclusive")
    return args


def main() -> int:
    """Run governance validation and print a concise evidence summary."""
    args = parse_args()
    if args.source_root:
        report, errors = run_source(args.source_root.resolve(), args.output)
        label = "source catalog"
    else:
        root = args.root.resolve() if args.root else Path(__file__).resolve().parents[1]
        report, errors = run_generated(root, args.output)
        label = str(report.get("governance_profile", "unknown"))
    print(f"Governance Gate: {label}")
    print(f"Status: {report.get('status', 'fail')}")
    required = report.get("required_controls")
    if isinstance(required, list):
        print(f"Required controls: {len(required)}")
    if errors:
        for error in errors:
            print(f"FAIL {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
