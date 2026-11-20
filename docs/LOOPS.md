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
- The loop layer is **opt-in**. A project rendered with `bootstrap.py --loop`
  receives the vendored schemas and the `loop-schema-vendor` and
  `loop-contracts` checks; a default render receives none of them. The
  selection is recorded as `loop` in `.harness.json`, and an upgrade keeps the
  layer of a project that already had it (see "Enabling the loop layer").
- With the layer enabled, `scripts/quality_gate.py`'s `loop-contracts` check
  validates any contract found under `.loop/contracts/**` against the schemas
  above; with no contracts present it is a documented no-op. Without the layer,
  a contract under `.loop/contracts/` fails both the quality gate and
  `bootstrap.py --check`, so a contract is never silently left unvalidated.
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
   `evidence` collection (hashed commands, hashed output, the
   repository, OID algorithm, and complete `baseline_oid`/`candidate_oid`),
   and a `verdict` derived by grading that
   evidence against the contract's `acceptance.hard_gates`.
3. **Operational-level** -- the loop's own health across many runs: budget
   burn, escalation rate, and drift between what a contract declares and
   what actually happens.

## Non-negotiable principles

- A builder never certifies its own result. Only a mechanically-derived
  `verdict` can.
- A hard gate is default-FAIL and must reduce to a command with an exit
  code. The contract-addressable hard gates
  (`acceptance.hard_gates`) are exactly the named checks this harness's own
  `quality_gate.py` implements: `lock`, `lint`, `format`, `typing`,
  `tests`, `security`, `dependencies`, `architecture`, `mcp`, `governance`.
  When the loop layer is enabled, separate mandatory infrastructure checks,
  `loop-schema-vendor` and `loop-contracts`, always protect provenance,
  integrity, and contract validation; they are not arbitrary commands
  selectable by a builder.
- Evidence is bound to the repository, complete Git object IDs
  (`baseline_oid`, `candidate_oid`), the contract, policy, and candidate-tree
  hashes, shell-free command `argv`, and a hashed executor environment, so a
  verdict can always be traced back to exactly what ran against exactly what
  code (evidence wire format `2.0.0`).
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

`template/scripts/_vendor_loop_schemas/` is a deterministic bundle rendered from
`engineering-loop-schemas v0.3.0` at the full commit
`5340d491b46f4fabc967c81bb3e5204104b6b5d8` with that repository's
`scripts/render_vendor_bundle.py`. Its `manifest.json` (manifest format `2.0.0`) records the
source repository, version, commit, and the size and SHA-256 hash of every Python source and of
the four canonical JSON Schemas, plus each declared import adaptation. `loop-schema-vendor` also
rejects any file in the bundle that the manifest does not declare.

The bundle is not a byte-for-byte copy. During rendering, the package imports in
`validate_contract.py` change from `loop_schemas` to `_vendor_loop_schemas`; this keeps the
vendored package isolated and avoids collision with the protected `scripts/loop_*` namespace. The
adaptation is explicit in the manifest and covered by deterministic-rendering, integrity, and
tampering tests. `loop-schema-vendor` verifies the bundle offline on every generated-project
quality run. Fix the canonical schemas repository and render a new version instead of editing the
bundle manually.

`validate_contract.py` is stdlib-only. Reading a YAML contract requires
PyYAML to be importable in the environment `scripts/quality_gate.py` runs
in; JSON contracts always work with no extra dependency. PyYAML is
deliberately **not** added as a harness dependency by this integration
(the shared core is in feature freeze -- see `CONTRIBUTING.md`); if a human
wants YAML contracts validated locally, they add PyYAML to their own
project themselves.

## Enabling the loop layer

Render a new project with the layer:

```bash
python3 bootstrap.py --name payments-api --package payments_api \
  --target ../payments-api --loop
```

Add it to an existing project with `--merge --loop`, or remove it with `--merge --no-loop`.
Without either flag, `--merge` keeps the previous selection; a project rendered before the layer
became opt-in, whose `.harness.json` has no `loop` key but tracks the vendored bundle, keeps the
layer. Disabling never deletes files: the bootstrap lists the previously generated loop files left
in place, and the quality gate keeps running their checks until a human removes them.

The layer only validates contracts; it does not run a loop. The `.loop/**` and `scripts/loop_*`
write denylist in the hooks applies whether or not the layer is enabled.

## Out of scope for this integration

Per the approved plan, this phase does **not** add a loop runner, a gate
executor, a state machine, an evaluator, or any autonomy above `report`.
It also does not create the future unified harness or an `alicerce` CLI.
Those are follow-on work once Sprint 0 and this foundation are reviewed.
