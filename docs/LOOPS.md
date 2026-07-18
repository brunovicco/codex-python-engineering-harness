# Evidence-Gated Engineering Loops

This harness's shared loop contract, evidence, verdict, and builder-result
schemas live in a separate repository,
[`engineering-loop-schemas`](https://github.com/brunovicco/engineering-loop-schemas),
so both this harness and its sibling
(`claude-python-engineering-harness`) validate loop contracts against one
canonical source instead of drifting copies. That repository is also the
embryo of the future unified ("alicerce") harness's loop layer.

## Current state: Phase 1, report-only

Loop autonomy in this harness is currently **`report`** and nothing higher.
Concretely, as of this integration:

- No agent in this repository or a project generated from it can promote a
  candidate change, run a loop end to end, or certify its own work.
- `loop_runner.py`, `loop_gate.py`, `loop_state.py`, an evaluator, or any
  kind of state machine do not exist. Building them is explicitly out of
  scope for this phase.
- `.loop/**` and `scripts/loop_*` are denylisted for agent writes by
  `protect_sensitive_files.py` (see `.codex/hooks/protect_sensitive_files.py`
  in a generated project). Only a human, editing outside of an agent tool
  call, is expected to place a real contract under `.loop/contracts/`.
- `scripts/quality_gate.py`'s `loop-contracts` check validates any contract
  found under `.loop/contracts/**` against the schemas above. With no
  contracts present -- the expected state today -- it is a documented no-op.
- The self-evaluation CI workflow (see the repository's `.github/workflows/`)
  that renders every profile and reports gate results is itself report-only:
  it never modifies repository code, and its optional agent-interpretation
  step is disabled by default behind a flag with no credentials in the repo.

## The three-tier model

Every loop run belongs to one of three levels of scrutiny, mirrored from
`engineering-loop-schemas`' README:

1. **Agent-level** -- a single builder attempt against one contract. Its
   output is a `builder-result` document: the builder's own account of what
   it attempted, explicitly marked non-authoritative.
2. **Completion-level** -- one full run: builder attempt(s), mechanical
   `evidence` collection (hashed commands, hashed output, exact
   `baseline_sha`/`candidate_sha`), and a `verdict` derived by grading that
   evidence against the contract's `acceptance.hard_gates`.
3. **Operational-level** -- the loop's own health across many runs: budget
   burn, escalation rate, and drift between what a contract declares and
   what actually happens.

## Non-negotiable principles

- A builder never certifies its own result. Only a mechanically-derived
  `verdict` can.
- A hard gate is default-FAIL and must reduce to a command with an exit
  code. The set of hard gates a contract may reference
  (`acceptance.hard_gates`) is exactly the named checks this harness's own
  `quality_gate.py` implements: `lock`, `lint`, `format`, `typing`,
  `tests`, `security`, `dependencies`, `architecture`, `mcp`, `governance`.
- Evidence is bound to exact commits (`baseline_sha`, `candidate_sha`) and
  a hashed environment (`uv_lock_sha256`), so a verdict can always be
  traced back to exactly what ran against exactly what code.
- Hooks (`protect_sensitive_files.py`, `validate_bash.py`, `guard_mcp.py`)
  are defense in depth, not orchestration. They stop an agent from silently
  exceeding this phase's declared scope; they do not run, schedule, or
  promote anything.

## Final states

Every completed run resolves to exactly one final state
(`verdict.final_state`):

| State | Meaning |
| --- | --- |
| `SUCCEEDED` | All hard gates passed; candidate is promotable pending human review. |
| `NO_OP` | The builder correctly determined there was nothing to do. |
| `NO_PROGRESS` | The builder produced a candidate, but it does not improve on baseline. |
| `VERIFY_FAILED` | One or more hard gates failed against the candidate. |
| `POLICY_BLOCKED` | The candidate touched `scope.denylist` or an `actions.denied` entry. |
| `BUDGET_EXCEEDED` | `budgets` (tokens, cost, wall clock, or command count) was exceeded. |
| `ESCALATED` | The run could not resolve PASS/FAIL and needs a human decision. |
| `INFRA_FAILED` | The run failed for reasons unrelated to the candidate (tooling, network, environment). |

## Vendoring

`scripts/_vendor_loop_schemas/` (and its `template/scripts/` copy shipped
to generated projects) is a verbatim vendored copy of
`engineering-loop-schemas`' `src/loop_schemas/` at a pinned commit, recorded
in a header comment in each vendored file. Re-vendor from the source
repository rather than hand-editing; the one intentional deviation (the
package directory is named `_vendor_loop_schemas`, not `loop_schemas`, so
it does not collide with the `scripts/loop_*` denylist above) is documented
in that same header.

`validate_contract.py` is stdlib-only. Reading a YAML contract requires
PyYAML to be importable in the environment `scripts/quality_gate.py` runs
in; JSON contracts always work with no extra dependency. PyYAML is
deliberately **not** added as a harness dependency by this integration
(the shared core is in feature freeze -- see `CONTRIBUTING.md`); if a human
wants YAML contracts validated locally, they add PyYAML to their own
project themselves.

## Out of scope for this integration

Per the approved plan, this phase does **not** add a loop runner, a gate
executor, a state machine, an evaluator, or any autonomy above `report`.
It also does not create the future unified harness or an `alicerce` CLI.
Those are follow-on work once Sprint 0 and this foundation are reviewed.
