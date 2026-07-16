# Upgrading generated projects

Generated projects are snapshots and are never modified automatically.

## Recommended workflow

1. Read `CHANGELOG.md` and confirm the target harness version.
2. Commit or otherwise preserve the generated project's current state.
3. Run a preview from the new harness checkout:

   ```bash
   python /path/to/harness/bootstrap.py --target . --dry-run --merge
   ```

4. Apply the non-destructive update:

   ```bash
   python /path/to/harness/bootstrap.py --target . --merge
   ```

5. Review every `*.harness-new` conflict file. The harness preserves locally customized files and
   never treats the conflict copy as an automatic replacement.
6. Run the generated project's gate and metadata check:

   ```bash
   uv sync --all-groups
   uv run python scripts/quality_gate.py
   python /path/to/harness/bootstrap.py --target . --check
   ```

7. Review and trust changed Codex hooks before using them.

## Plugin upgrades

Plugin releases are independent from generator releases. Update the marketplace installation,
restart Codex when required, review changed hooks and permissions, and validate the plugin before
adopting it. A plugin update does not rewrite generated projects.

Do not copy manifest hashes, delete conflict files without review, or replace customized project
files merely to make `--check` pass.
