#!/usr/bin/env python3
"""Validate Codex project MCP configuration for portability and security."""

import re
import sys
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CONFIG_FILE = Path(".codex/config.toml")
ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")
SENSITIVE_NAME = re.compile(
    r"(?:authorization|cookie|credential|password|passwd|private[_-]?key|secret|token|api[_-]?key)",
    re.IGNORECASE,
)
HIGH_CONFIDENCE_SECRET = re.compile(
    r"(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{20,})"
)
SHELL_COMMANDS = {"bash", "cmd", "fish", "powershell", "pwsh", "sh", "zsh"}
EXACT_PYTHON_PACKAGE = re.compile(
    r"^[A-Za-z0-9_.-]+==[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$"
)


def error(path: Path, server: str, message: str) -> str:
    """Format one validation error."""
    return f"{path}:{server}: {message}"


def validate_timeout(path: Path, name: str, config: dict[str, Any], key: str) -> list[str]:
    """Require one bounded timeout in seconds."""
    value = config.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 < value <= 600:
        return [error(path, name, f"{key} must be a number greater than 0 and at most 600")]
    return []


def validate_runner(path: Path, name: str, command: str, args: list[str]) -> list[str]:
    """Require exact package versions for ephemeral package runners."""
    executable = Path(command).name.lower()
    if executable == "uvx":
        if "--from" in args:
            index = args.index("--from")
            package = args[index + 1] if index + 1 < len(args) else ""
        else:
            package = next((value for value in args if not value.startswith("-")), "")
        if not EXACT_PYTHON_PACKAGE.fullmatch(package):
            return [error(path, name, "uvx package must use an exact == version")]
    if executable == "npx":
        package = next((value for value in args if not value.startswith("-")), "")
        separator = package.rfind("@")
        version = package[separator + 1 :] if separator > 0 else ""
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?", version):
            return [error(path, name, "npx package must include an exact @version")]
    return []


def validate_stdio(path: Path, name: str, config: dict[str, Any]) -> list[str]:
    """Validate one Codex STDIO MCP server."""
    errors = validate_timeout(path, name, config, "startup_timeout_sec")
    command = config.get("command")
    args = config.get("args", [])
    if not isinstance(command, str) or not command:
        errors.append(error(path, name, "STDIO server requires a non-empty command"))
    elif Path(command).name.lower() in SHELL_COMMANDS:
        errors.append(error(path, name, "shell wrappers are not allowed as STDIO commands"))
    if not isinstance(args, list) or not all(isinstance(value, str) for value in args):
        errors.append(error(path, name, "args must be an array of strings"))
    elif isinstance(command, str):
        errors.extend(validate_runner(path, name, command, args))
        for index, value in enumerate(args):
            if HIGH_CONFIDENCE_SECRET.search(value):
                errors.append(error(path, name, f"argument {index} contains a probable secret"))
            flag = value.partition("=")[0].lstrip("-")
            if value.startswith("-") and SENSITIVE_NAME.search(flag):
                errors.append(
                    error(
                        path,
                        name,
                        f"sensitive argument {value!r} is not allowed; forward an env_var instead",
                    )
                )

    env = config.get("env", {})
    if not isinstance(env, dict):
        errors.append(error(path, name, "env must be a table"))
    else:
        for variable, value in env.items():
            if not isinstance(value, str):
                errors.append(error(path, name, f"environment value {variable!r} must be a string"))
            elif SENSITIVE_NAME.search(variable) or HIGH_CONFIDENCE_SECRET.search(value):
                errors.append(
                    error(
                        path,
                        name,
                        f"sensitive environment value {variable!r} must be forwarded with env_vars",
                    )
                )

    env_vars = config.get("env_vars", [])
    if not isinstance(env_vars, list) or not all(
        isinstance(value, str) and ENV_NAME.fullmatch(value) for value in env_vars
    ):
        errors.append(error(path, name, "env_vars must contain environment-variable names only"))
    return errors


def validate_remote(path: Path, name: str, config: dict[str, Any]) -> list[str]:
    """Validate one streamable HTTP MCP server."""
    errors: list[str] = []
    url = config.get("url")
    if not isinstance(url, str) or not url:
        return [error(path, name, "HTTP server requires a non-empty url")]
    parsed = urlparse(url)
    localhost = parsed.hostname in {"127.0.0.1", "::1", "localhost"}
    if parsed.scheme != "https" and not localhost:
        errors.append(error(path, name, "remote URL must use https outside localhost"))
    if parsed.username is not None or parsed.password is not None:
        errors.append(error(path, name, "remote URL must not contain user information"))

    token_variable = config.get("bearer_token_env_var")
    if token_variable is not None and (
        not isinstance(token_variable, str) or ENV_NAME.fullmatch(token_variable) is None
    ):
        errors.append(error(path, name, "bearer_token_env_var must name an environment variable"))

    static_headers = config.get("http_headers", {})
    if not isinstance(static_headers, dict):
        errors.append(error(path, name, "http_headers must be a table"))
    else:
        for header, value in static_headers.items():
            if not isinstance(value, str):
                errors.append(error(path, name, f"header {header!r} must be a string"))
            elif SENSITIVE_NAME.search(header) or HIGH_CONFIDENCE_SECRET.search(value):
                errors.append(
                    error(path, name, f"sensitive header {header!r} must use env_http_headers")
                )

    env_headers = config.get("env_http_headers", {})
    if not isinstance(env_headers, dict) or not all(
        isinstance(value, str) and ENV_NAME.fullmatch(value) for value in env_headers.values()
    ):
        errors.append(
            error(path, name, "env_http_headers values must be environment-variable names")
        )
    return errors


def validate_server(path: Path, name: str, config: Any) -> list[str]:
    """Validate one server entry using the native Codex config shape."""
    if not isinstance(config, dict):
        return [error(path, name, "server configuration must be a table")]
    errors = validate_timeout(path, name, config, "tool_timeout_sec")
    if "command" in config:
        errors.extend(validate_stdio(path, name, config))
    elif "url" in config:
        errors.extend(validate_remote(path, name, config))
    else:
        errors.append(error(path, name, "server requires command or url"))
    return errors


def main() -> int:
    """Validate the project-scoped Codex configuration when it exists."""
    if not CONFIG_FILE.is_file():
        print("No .codex/config.toml found; nothing to validate.")
        return 0
    try:
        with CONFIG_FILE.open("rb") as handle:
            document = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"MCP configuration validation failed: {exc}", file=sys.stderr)
        return 1

    servers = document.get("mcp_servers", {})
    if not isinstance(servers, dict):
        print("MCP configuration validation failed: mcp_servers must be a table", file=sys.stderr)
        return 1
    errors = [
        item
        for name, config in servers.items()
        for item in validate_server(CONFIG_FILE, name, config)
    ]
    if errors:
        print("MCP configuration validation failed:", file=sys.stderr)
        for item in errors:
            print(f"- {item}", file=sys.stderr)
        return 1
    print(f"MCP configuration validation passed: {len(servers)} server(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
