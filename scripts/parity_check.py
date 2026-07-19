#!/usr/bin/env python3
"""Verify that parity-required artifacts exist or are declared intentional divergences.

The two sibling Python engineering harnesses must not drift silently.
``parity-manifest.json`` lists the family-independent artifacts both repositories are
expected to ship; family-specific artifacts (hooks, plugin, and marketplace manifests)
are derived at runtime from the detected family so the manifest stays byte-identical in
both repositories. ``parity-exceptions.json`` declares intentional divergences with a
reason. This script fails when a required artifact is missing for the local family and
is not covered by a declared exception.

Both harnesses carry byte-identical copies of this script and of the manifest; the
exceptions file is repository-specific. Update the manifest in both repositories in the
same change.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "parity-manifest.json"
EXCEPTIONS = ROOT / "parity-exceptions.json"


def family_artifacts(family: str) -> dict[str, str]:
    """Return family-specific artifact paths, built without family-name literals."""
    dot = "." + family
    if family == "codex":
        return {
            "template-hooks": f"template/{dot}/hooks/validate_bash.py",
            "plugin-manifest": f"plugins/python-engineering-harness/{dot}-plugin/plugin.json",
            "marketplace-manifest": ".agents/plugins/marketplace.json",
        }
    return {
        "template-hooks": f"template/{dot}/hooks/validate_bash.py",
        "plugin-manifest": f"plugin/python-engineering-harness/{dot}-plugin/plugin.json",
        "marketplace-manifest": f"{dot}-plugin/marketplace.json",
    }


def detect_family() -> str:
    """Detect which harness family this repository belongs to."""
    for candidate in ("claude", "codex"):
        if (ROOT / family_artifacts(candidate)["marketplace-manifest"]).is_file():
            return candidate
    raise SystemExit("parity: cannot detect harness family (no marketplace manifest found)")


def load_json(path: Path) -> dict:
    """Load one JSON document or exit with a readable error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"parity: missing {path.name}") from None
    except json.JSONDecodeError as error:
        raise SystemExit(f"parity: invalid JSON in {path.name}: {error}") from None


def main() -> int:
    """Check every required artifact for the local family."""
    family = detect_family()
    manifest = load_json(MANIFEST)
    exceptions = load_json(EXCEPTIONS)

    declared: dict[str, str] = {}
    for entry in exceptions.get("exceptions", []):
        identifier, reason = entry.get("id"), entry.get("reason")
        if not identifier or not reason:
            print(f"parity: exception without id or reason: {entry}", file=sys.stderr)
            return 1
        declared[identifier] = reason

    required: dict[str, str] = {}
    for artifact in manifest.get("artifacts", []):
        identifier, relative = artifact.get("id"), artifact.get("path")
        if not identifier or not relative:
            print(f"parity: manifest artifact without id or path: {artifact}", file=sys.stderr)
            return 1
        required[identifier] = relative
    required.update(family_artifacts(family))

    missing: list[str] = []
    checked = 0
    for identifier, relative in required.items():
        if identifier in declared:
            continue
        checked += 1
        if not (ROOT / relative).exists():
            missing.append(f"{identifier}: {relative}")

    if missing:
        print(
            f"parity: {len(missing)} required artifact(s) missing for family '{family}':",
            file=sys.stderr,
        )
        for item in missing:
            print(f"- {item}", file=sys.stderr)
        print(
            "Add the artifact or declare an exception with a reason in parity-exceptions.json.",
            file=sys.stderr,
        )
        return 1

    print(
        f"parity: {checked} artifacts present for family '{family}' "
        f"({len(declared)} declared exceptions)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
