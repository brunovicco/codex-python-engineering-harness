# Project governance records

This directory contains project-owned governance records. The bootstrap owns the catalog snapshot,
schemas, and selected profile manifest; project teams own `scope.json`, inventories, risks,
assessments, and exceptions.

Mappings indicate support for external frameworks. They do not make the project or organization
compliant or certified. Keep evidence metadata-only: do not include prompts, responses, source
content, credentials, tokens, personal data, or production data.

Run the deterministic check with:

```bash
uv run python scripts/governance_gate.py
```

The report is written to `build/governance-evidence/governance-report.json`.
