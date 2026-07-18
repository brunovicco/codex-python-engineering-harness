"""Canonical sensitive-path patterns shared by every Codex protection hook.

`protect_sensitive_files.py` (apply_patch/Edit/Write), `validate_bash.py`
(Bash and unified `exec_command`), and `guard_mcp.py` (`mcp__*` tool calls)
all import from this module so the set of blocked secrets never drifts
between the tool paths that can read, write, or shell out to sensitive
files.

Codex's tool surface has no dedicated read/search/list function tools
(unlike editor-integrated agents that expose `Read`/`Grep`/`Glob`). Per the
upstream hook tool-coverage table
(https://developers.openai.com/codex/hooks#tool-coverage), file inspection
in Codex happens through the `Bash` tool (`cat`, `grep`, `rg`, `find`, ad
hoc scripts, ...), through `apply_patch` context hunks, or through MCP
tools such as a filesystem server. Read protection is therefore achieved by
covering those three surfaces identically rather than by adding matchers
for tool names Codex does not expose.
"""

import fnmatch
import re

DENIED_GLOBS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "**/.env",
    "**/.env.*",
    "**/secrets/**",
    "**/credentials/**",
    "**/.ssh/**",
    "**/.aws/**",
    "**/.azure/**",
    "**/.config/gcloud/**",
    "**/*.pem",
    "**/*.key",
    "**/id_rsa",
    "**/id_rsa.*",
    "**/id_ed25519",
    "**/id_ed25519.*",
    "**/*credentials*.json",
    "**/*secret*.json",
    "**/terraform.tfstate*",
)

ALLOWED_GLOBS: tuple[str, ...] = (
    ".env.example",
    "**/.env.example",
    "**/*credentials*.example.*",
    "**/*secret*.example.*",
)

# Free-text form of the same denylist, for scanning raw shell command
# strings and MCP argument values that are not necessarily well-formed
# relative paths (env expansions, quoting, embedded flags, ...).
SENSITIVE_TOKEN = re.compile(
    r"(?:^|[/\\\s'\"=])(?:"
    r"\.env(?!\.example)(?:\.[A-Za-z0-9_-]+)?|"
    r"id_(?:rsa|ed25519)(?:\.[A-Za-z0-9_-]+)?|"
    r"terraform\.tfstate(?:\.[A-Za-z0-9_-]+)?|"
    r"(?:secrets?|credentials?)(?:/|\\)|"
    r"\.ssh(?:/|\\)|"
    r"\.aws(?:/|\\)|"
    r"\.azure(?:/|\\)|"
    r"\.config(?:/|\\)gcloud(?:/|\\)|"
    r"[\w.-]*credentials[\w.-]*\.json|"
    r"[\w.-]*secret[\w.-]*\.json|"
    r"[^/\\\s'\"=]+\.pem\b|"
    r"[^/\\\s'\"=]+\.key\b"
    r")",
    re.IGNORECASE,
)


def matches_denied_path(path: str) -> bool:
    """Return whether a normalized relative or absolute path is sensitive."""
    normalized = path.replace("\\", "/")
    if any(fnmatch.fnmatch(normalized, pattern) for pattern in ALLOWED_GLOBS):
        return False
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in DENIED_GLOBS)


def references_sensitive_token(text: str) -> bool:
    """Return whether free text (shell command, MCP argument) names a secret."""
    if not text:
        return False
    normalized = text.replace("\\", "/")
    if any(fnmatch.fnmatch(normalized, pattern) for pattern in ALLOWED_GLOBS):
        return False
    return SENSITIVE_TOKEN.search(text) is not None
