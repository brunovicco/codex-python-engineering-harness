#!/usr/bin/env python3
"""Validate every Evidence-Gated Engineering Loop contract under .loop/contracts/.

Part of the Phase 0-1 (report-only) loop foundation described in
docs/LOOPS.md. This check is intentionally a no-op when no contracts exist
yet -- .loop/ is denylisted for agent writes by protect_sensitive_files.py
in this phase, so only a human is expected to place a contract there. Once
one exists, this check keeps it schema-valid as part of the regular
quality gate, using the vendored validator in _vendor_loop_schemas/ (see
that directory for its origin and pinned version).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _vendor_loop_schemas.validate_contract import (  # path setup above
    ContractValidationError,
    load_document,
    validate,
)

CONTRACTS_GLOB = ".loop/contracts/**/*"
CONTRACT_SUFFIXES = {".json", ".yaml", ".yml"}


def find_contracts(root: Path) -> list[Path]:
    """Return every contract file under .loop/contracts/, if any."""
    contracts_dir = root / ".loop" / "contracts"
    if not contracts_dir.is_dir():
        return []
    return sorted(
        path
        for path in contracts_dir.rglob("*")
        if path.is_file() and path.suffix in CONTRACT_SUFFIXES
    )


def main() -> int:
    """Validate every discovered contract; skip cleanly if none exist."""
    root = Path(__file__).resolve().parents[1]
    contracts = find_contracts(root)
    if not contracts:
        print(
            "No loop contracts found under .loop/contracts/ "
            "(expected while loop autonomy is 'report' -- Phase 0-1). Skipping."
        )
        return 0

    failures: list[str] = []
    for contract_path in contracts:
        try:
            document = load_document(contract_path)
        except ContractValidationError as exc:
            failures.append(f"{contract_path}: {exc}")
            continue
        errors = validate(document)
        if errors:
            failures.append(f"{contract_path}: " + "; ".join(errors))
        else:
            print(f"{contract_path}: valid")

    if failures:
        print("\nInvalid loop contract(s):", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
