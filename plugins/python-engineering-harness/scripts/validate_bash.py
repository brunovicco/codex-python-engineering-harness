#!/usr/bin/env python3
"""Block destructive or credential-exposing shell commands."""

import fnmatch
import re
import shlex

from _common import deny_tool, log_event, read_input, run_pre_tool_hook
from sensitive_patterns import references_sensitive_token

RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(^|[;&|]\s*)sudo\b", re.IGNORECASE), "sudo is not allowed from Codex"),
    (re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE), "git reset --hard is destructive"),
    (
        re.compile(r"\bgit\s+clean\s+-(?:[^\s]*f[^\s]*d|[^\s]*d[^\s]*f)", re.IGNORECASE),
        "git clean -fd is destructive",
    ),
    (
        re.compile(r"\bgit\s+push\b[^\n]*(?:--force|-f\b|\s\+\S)", re.IGNORECASE),
        "force push is not allowed",
    ),
    (
        re.compile(r"\brm\s+-[^\n]*r[^\n]*f\s+(?:/|~|\.|\.\.|\$HOME)(?:\s|$)", re.IGNORECASE),
        "recursive deletion of a broad path is blocked",
    ),
    (
        re.compile(r"\bchmod\s+(?:-R\s+)?777\b", re.IGNORECASE),
        "world-writable permissions are blocked",
    ),
    (
        re.compile(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:bash|sh|zsh)\b", re.IGNORECASE),
        "piping remote content directly to a shell is blocked",
    ),
    (
        re.compile(r"\bterraform\s+destroy\b", re.IGNORECASE),
        "terraform destroy requires an explicit human-controlled workflow",
    ),
    (
        re.compile(
            r"\bcodex\s+mcp\s+add\b[^\n]*(?:--header|-H|--env|-e)[^\n]*(?:Bearer|token|secret|password|api[_-]?key)",
            re.IGNORECASE,
        ),
        "MCP credentials must not be passed as command-line literals",
    ),
    (
        re.compile(r"\bkubectl\s+delete\s+(?:namespace|ns)\b", re.IGNORECASE),
        "namespace deletion is blocked",
    ),
    (
        re.compile(r"\bdocker\s+system\s+prune\b[^\n]*-a", re.IGNORECASE),
        "global Docker pruning is blocked",
    ),
    (
        re.compile(r"\b(?:mkfs|fdisk)\b|\bdd\s+if=", re.IGNORECASE),
        "low-level disk operations are blocked",
    ),
)

SHELL_SEPARATORS = frozenset({";", "&", "&&", "|", "||"})
JQ_OPTIONS_WITH_ONE_VALUE = frozenset({"-L", "--library-path", "--indent"})
JQ_OPTIONS_WITH_TWO_VALUES = frozenset(
    {"--arg", "--argjson", "--argfile", "--slurpfile", "--rawfile"}
)
JQ_FILE_FILTER_OPTIONS = frozenset({"-f", "--from-file"})


def shell_tokens(command: str) -> list[str]:
    """Split a command while preserving shell control operators."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def _literal_is_sensitive(value: str) -> bool:
    """Match one concrete word against the shared sensitive-path denylist."""
    return references_sensitive_token(value)


SHELL_INTERPRETERS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
MAX_NESTING = 3
MAX_BRACE_VARIANTS = 64
GLOB_CHARACTERS = frozenset("*?[")
BRACE_GROUP = re.compile(r"\{([^{}]*,[^{}]*)\}")
# Concrete names a shell glob could expand to; kept aligned with the sensitive-path denylist.
SENSITIVE_NAMES = (
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.staging",
    ".env.test",
    ".ssh",
    ".aws",
    "id_rsa",
    "id_ed25519",
    "terraform.tfstate",
    "secrets",
    "credentials",
)


def expand_braces(token: str) -> list[str]:
    """Expand non-nested shell brace groups such as ``.{e,x}nv`` into concrete words."""
    variants = [token]
    while True:
        expanded: list[str] = []
        changed = False
        for variant in variants:
            match = BRACE_GROUP.search(variant)
            if match is None:
                expanded.append(variant)
                continue
            changed = True
            prefix, suffix = variant[: match.start()], variant[match.end() :]
            expanded.extend(prefix + option + suffix for option in match.group(1).split(","))
        variants = expanded[:MAX_BRACE_VARIANTS]
        if not changed or len(expanded) >= MAX_BRACE_VARIANTS:
            return variants


def glob_matches_sensitive_name(token: str) -> bool:
    """Return whether a glob component could expand to a sensitive file name.

    Shell semantics apply: a pattern that does not start with a dot never matches a dotfile, and
    patterns with fewer than two literal characters (``*``, ``?*``) are ignored as too broad.
    """
    for component in token.replace("\\", "/").split("/"):
        if GLOB_CHARACTERS.isdisjoint(component):
            continue
        literals = sum(character not in "*?[]!^" for character in component)
        if literals < 2:
            continue
        for name in SENSITIVE_NAMES:
            if name.startswith(".") and not component.startswith("."):
                continue
            if fnmatch.fnmatchcase(name.lower(), component.lower()):
                return True
    return False


def token_is_sensitive(token: str) -> bool:
    """Check a word, its brace expansions, and any glob for sensitive targets."""
    return any(
        _literal_is_sensitive(variant) or glob_matches_sensitive_name(variant)
        for variant in expand_braces(token)
    )


def command_views(command: str, depth: int = 0) -> list[str]:
    """Return the raw command, its unquoted form, and nested ``sh -c``/``eval`` payloads.

    Quote concatenation (``--ha""rd``) and interpreter wrappers (``bash -c '...'``) otherwise hide
    a command from pattern rules that read the raw text.
    """
    try:
        tokens = shell_tokens(command)
    except ValueError:
        return [command]
    views = [command, " ".join(tokens)]
    if depth >= MAX_NESTING:
        return views
    for index, token in enumerate(tokens):
        name = token.rsplit("/", maxsplit=1)[-1]
        if name in SHELL_INTERPRETERS:
            cursor = index + 1
            while cursor < len(tokens) and tokens[cursor].startswith("-"):
                option = tokens[cursor]
                if not option.startswith("--") and "c" in option[1:]:
                    if cursor + 1 < len(tokens):
                        views.extend(command_views(tokens[cursor + 1], depth + 1))
                    break
                cursor += 1
        elif name == "eval":
            payload: list[str] = []
            for word in tokens[index + 1 :]:
                if word in SHELL_SEPARATORS:
                    break
                payload.append(word)
            if payload:
                views.extend(command_views(" ".join(payload), depth + 1))
    return views


def jq_filter_indexes(tokens: list[str]) -> set[int]:
    """Return inline jq program positions, which are expressions rather than paths."""
    filters: set[int] = set()
    for index, token in enumerate(tokens):
        if token.rsplit("/", maxsplit=1)[-1] != "jq":
            continue

        cursor = index + 1
        uses_file_filter = False
        while cursor < len(tokens) and tokens[cursor] not in SHELL_SEPARATORS:
            option = tokens[cursor]
            if option == "--":
                cursor += 1
                break
            if option in JQ_FILE_FILTER_OPTIONS:
                uses_file_filter = True
                cursor += 2
                continue
            if option in JQ_OPTIONS_WITH_TWO_VALUES:
                cursor += 3
                continue
            if option in JQ_OPTIONS_WITH_ONE_VALUE:
                cursor += 2
                continue
            if option.startswith("-"):
                cursor += 1
                continue
            break

        if not uses_file_filter and cursor < len(tokens) and tokens[cursor] not in SHELL_SEPARATORS:
            filters.add(cursor)
    return filters


def references_sensitive_path(command: str) -> bool:
    """Detect sensitive path arguments without treating jq selectors as file paths."""
    tokens = shell_tokens(command)
    ignored = jq_filter_indexes(tokens)
    return any(
        token_is_sensitive(token) for index, token in enumerate(tokens) if index not in ignored
    )


def main() -> None:
    """Inspect a Bash tool call and deny known dangerous patterns."""
    payload = read_input()
    tool_input = payload.get("tool_input", {})
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return

    views = command_views(command)
    if any(references_sensitive_path(view) for view in views):
        log_event(payload, "validate_bash", "sensitive-file", "deny")
        deny_tool(
            "Blocked command: shell commands may not reference sensitive files. "
            "Use an example file or environment-variable names only."
        )
        return

    for pattern, reason in RULES:
        if any(pattern.search(view) for view in views):
            log_event(payload, "validate_bash", "destructive-command", "deny")
            deny_tool(f"Blocked command: {reason}.")
            return


if __name__ == "__main__":
    run_pre_tool_hook(main)
