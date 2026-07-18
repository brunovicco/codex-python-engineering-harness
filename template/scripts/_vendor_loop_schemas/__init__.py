# Vendored from brunovicco/engineering-loop-schemas
# @ 75a63eef269fd995128ab39c89e551fe58a27bf7 (v0.1.0, includes the UP037/RUF100 lint fixes: a
# per-file-ignore for the load-bearing quoted return annotations, and
# removal of a stray noqa that was itself flagged once RUF is enabled).
# No published tag exists yet as of this vendoring; pinned to the commit
# above. Do not edit by hand -- re-vendor from the source repository
# instead. See docs/LOOPS.md for how this fits into the Phase 0-1
# report-only loop foundation.
# Adapted for vendoring: this directory is named `_vendor_loop_schemas`
# (not `loop_schemas`) so it does not itself match the `scripts/loop_*`
# out-of-scope-loop-path denylist in protect_sensitive_files.py; the
# `from loop_schemas...` imports were changed to
# `from _vendor_loop_schemas...` to match. No other lines were edited.
"""Evidence-Gated Engineering Loop schemas: models and a dependency-free validator.

This package is the canonical, shared contract between every engineering-loop
implementation (currently the Codex and claude-python-engineering-harness
Python engineering harnesses). It defines the shape of a loop `contract`,
the mechanical `evidence` a run produces, the `verdict` derived from grading that evidence, and the
non-authoritative `builder-result` a builder reports.

Everything here is Phase 0-1, report-only: no code in this package executes a
loop, promotes a candidate, or grants any agent the authority to certify its
own work. See README.md for the full model and the documented final states.
"""

from _vendor_loop_schemas.models import (
    Acceptance,
    Actions,
    Baseline,
    Budgets,
    Contract,
    HumanReview,
    Scope,
    Selection,
    Trigger,
)

__all__ = [
    "Acceptance",
    "Actions",
    "Baseline",
    "Budgets",
    "Contract",
    "HumanReview",
    "Scope",
    "Selection",
    "Trigger",
]

__version__ = "0.1.0"
