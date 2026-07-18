#!/usr/bin/env python3
"""Verify the offline integrity and provenance of vendored loop schemas."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, cast

COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_REPOSITORY = "brunovicco/engineering-loop-schemas"
REQUIRED_FILES = {"__init__.py", "models.py", "validate_contract.py"}


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for one file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(vendor_dir: Path) -> dict[str, Any]:
    """Load the local provenance manifest."""
    path = vendor_dir / "manifest.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("manifest.json must contain an object")
    return cast(dict[str, Any], document)


def validate_manifest(vendor_dir: Path) -> list[str]:
    """Return all integrity and provenance errors."""
    errors: list[str] = []
    try:
        manifest = load_manifest(vendor_dir)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"could not load manifest.json: {exc}"]

    if manifest.get("manifest_version") != "1.0.0":
        errors.append(f"unsupported manifest_version: {manifest.get('manifest_version')!r}")

    source = manifest.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
        source = {}

    repository = source.get("repository")
    version = source.get("version")
    commit = source.get("commit")
    if repository != EXPECTED_REPOSITORY:
        errors.append(f"unexpected source repository: {repository!r}")
    if not isinstance(version, str) or not SEMVER_PATTERN.fullmatch(version):
        errors.append(f"invalid source version: {version!r}")
    if not isinstance(commit, str) or not COMMIT_PATTERN.fullmatch(commit):
        errors.append(f"invalid source commit: {commit!r}")

    files = manifest.get("files")
    if not isinstance(files, dict):
        return [*errors, "files must be an object"]

    names = set(files)
    if names != REQUIRED_FILES:
        errors.append("manifest files must be exactly: " + ", ".join(sorted(REQUIRED_FILES)))

    for name in sorted(REQUIRED_FILES):
        metadata = files.get(name)
        if not isinstance(metadata, dict):
            errors.append(f"{name}: metadata must be an object")
            continue
        expected_hash = metadata.get("sha256")
        expected_size = metadata.get("size_bytes")
        if not isinstance(expected_hash, str) or not SHA256_PATTERN.fullmatch(expected_hash):
            errors.append(f"{name}: invalid sha256 in manifest")
            continue
        if not isinstance(expected_size, int) or expected_size < 0:
            errors.append(f"{name}: invalid size_bytes in manifest")
            continue

        path = vendor_dir / name
        if not path.is_file():
            errors.append(f"{name}: file is missing")
            continue
        actual_hash = sha256_file(path)
        actual_size = path.stat().st_size
        if actual_hash != expected_hash:
            errors.append(f"{name}: sha256 mismatch; expected {expected_hash}, got {actual_hash}")
        if actual_size != expected_size:
            errors.append(f"{name}: size mismatch; expected {expected_size}, got {actual_size}")

    validator = vendor_dir / "validate_contract.py"
    if validator.is_file():
        text = validator.read_text(encoding="utf-8")
        adapted = "from _vendor_loop_schemas.models import Contract"
        original = "from loop_schemas.models import Contract"
        if adapted not in text:
            errors.append("validate_contract.py: vendored package import is missing")
        if original in text:
            errors.append("validate_contract.py: source package import was not adapted")

    for name in ("models.py", "validate_contract.py"):
        path = vendor_dir / name
        if not path.is_file() or not isinstance(version, str) or not isinstance(commit, str):
            continue
        text = path.read_text(encoding="utf-8")
        if f"# Version: {version}" not in text:
            errors.append(f"{name}: provenance version header is missing")
        if f"# Commit: {commit}" not in text:
            errors.append(f"{name}: provenance commit header is missing")

    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Generated-project root; defaults to the parent of scripts/.",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Validate the generated project's local vendored bundle."""
    args = parse_args(argv)
    vendor_dir = args.root.resolve() / "scripts" / "_vendor_loop_schemas"
    errors = validate_manifest(vendor_dir)

    if args.as_json:
        print(
            json.dumps(
                {
                    "valid": not errors,
                    "vendor_dir": str(vendor_dir),
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        print("Vendored loop-schema integrity check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
    else:
        manifest = load_manifest(vendor_dir)
        source = cast(dict[str, Any], manifest["source"])
        print(f"Vendored loop-schema bundle is valid: {source['version']} @ {source['commit']}.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
