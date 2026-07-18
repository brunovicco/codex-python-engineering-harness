#!/usr/bin/env python3
"""Block Codex from reading or modifying sensitive files and out-of-scope loop paths."""

import fnmatch
from pathlib import Path
from typing import Any

from _common import deny_tool, log_event, project_root, read_input, run_pre_tool_hook
from sensitive_patterns import matches_denied_path

# Evidence-Gated Engineering Loop scaffolding is out of scope while loop
# autonomy is "report" (Phase 0-1): loop_runner.py, loop_gate.py, and
# loop_state.py must not be built yet (see docs/LOOPS.md), and .loop/ is
# reserved for future loop state and contracts that only a human -- not an
# agent under this hook -- should place there. This is a separate concern
# from the sensitive-file denylist above: it is not about secrecy, it is
# about keeping this repository's declared Phase 0-1 scope from being
# silently exceeded.
OUT_OF_SCOPE_PATTERNS = (
    ".loop/**",
    "scripts/loop_*",
)


def strings(value: Any) -> list[str]:
    """Collect string values recursively from tool input."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for key, nested in value.items():
            if key in {"file_path", "path", "notebook_path", "filename"}:
                result.extend(strings(nested))
        return result
    if isinstance(value, list):
        result = []
        for nested in value:
            result.extend(strings(nested))
        return result
    return []


def matches(path: str, patterns: tuple[str, ...]) -> bool:
    """Return whether a path matches one of the given glob patterns."""
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def candidate_paths(raw: str, root: Path) -> tuple[str, str]:
    """Return the root-relative display path and absolute posix path for raw."""
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        display = candidate.resolve().relative_to(root).as_posix()
    except ValueError:
        display = candidate.as_posix()
    return display, candidate.as_posix()


def main() -> None:
    """Deny tool use for sensitive file paths and out-of-scope loop paths."""
    payload = read_input()
    root = project_root(payload)
    tool_input = payload.get("tool_input", {})

    for raw in strings(tool_input):
        display, absolute = candidate_paths(raw, root)

        if matches_denied_path(display) or matches_denied_path(absolute):
            log_event(payload, "protect_sensitive_files", "sensitive-file", "deny")
            deny_tool(
                f"Access to sensitive path {raw!r} is blocked. "
                "Use an example file or an environment-variable name without secret values."
            )
            return

        if matches(display, OUT_OF_SCOPE_PATTERNS) or matches(absolute, OUT_OF_SCOPE_PATTERNS):
            log_event(payload, "protect_sensitive_files", "out-of-scope-loop-path", "deny")
            deny_tool(
                f"Path {raw!r} is Evidence-Gated Engineering Loop scaffolding, which is out of "
                "scope while loop autonomy is 'report' (Phase 0-1). See docs/LOOPS.md. "
                "loop_runner.py, loop_gate.py, loop_state.py, and .loop/ contents are not to be "
                "built by an agent in this phase."
            )
            return


if __name__ == "__main__":
    run_pre_tool_hook(main)
