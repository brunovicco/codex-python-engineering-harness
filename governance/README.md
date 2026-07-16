# Governance source model

This directory is owned by the harness and is not copied wholesale into generated projects.
`catalog/controls.json` is the canonical control catalog. Profiles select controls by capability;
overlays add regulatory or organizational requirements. The bootstrap materializes a versioned
snapshot and the applicable schemas into projects with governance enabled.

Mappings describe how a harness control supports a framework reference. They are many-to-many,
may be partial, and never constitute a claim that a repository or organization is compliant or
certified. Licensed standards are represented only by identifiers and original harness-authored
descriptions.

Validate the source model with:

```bash
uv run python template/scripts/governance_gate.py --source-root .
```
