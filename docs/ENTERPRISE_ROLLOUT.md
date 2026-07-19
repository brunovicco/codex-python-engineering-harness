# Enterprise rollout

*[Português](ENTERPRISE_ROLLOUT.pt-BR.md)*

Use the repository scaffold for project-specific policy and the plugin marketplace for reusable
capabilities.

## Recommended ownership

- Platform engineering owns the plugin, hook runtime, approved configuration, and CI baseline.
- Security owns blocked paths, dangerous command patterns, secret patterns, and exception
  governance.
- Architecture owns dependency contracts and the standard ADR template.
- Each product team owns its `AGENTS.md`, project configuration, data inventory, and acceptance
  criteria.

## Distribution model

1. Publish this repository in a controlled internal Git host.
2. Add it as an internal marketplace
   (`codex plugin marketplace add <internal-git-or-path>`).
3. Validate and version the plugin before promotion.
4. Pin or approve versions through your configuration-management baseline where available.
5. Roll out first to a pilot group and inspect denials, false positives, latency, and developer
   overrides.
6. Promote only after the generated project and plugin pass the validation checklist.

## Separation of concerns

- Keep project facts and commands in the repository (`AGENTS.md`, `.codex/config.toml`).
- Keep reusable procedures and skills in the plugin.
- Keep mandatory controls in hooks, sandboxing, CI, identity, network, and repository protection.
- Require explicit trust of `.codex/config.toml` and `.codex/hooks.json`; review new or changed
  hooks with `/hooks` before trusting them.
- Do not place credentials in plugin settings or MCP configuration.
- Treat MCP servers and external integrations as data egress paths that require an explicit
  threat model.

## MCP rollout model

Treat MCP as an integration platform, not a developer convenience toggle. Recommended progression:

1. Inventory the external system, owner, data classes, operations, authentication, and retention.
2. Pilot with a read-only identity and non-production data.
3. Review the server implementation, release process, dependency pinning, prompt-injection
   exposure, and network destinations.
4. Publish approved project servers through `[mcp_servers.*]` in `.codex/config.toml`; the
   project validator enforces TLS, environment-name credential indirection, exact
   ephemeral-runner versions, direct STDIO commands, and bounded timeouts.
5. Keep credentials per user through environment indirection or a credential helper. Never place
   secrets in shared configuration.
6. Monitor server and tool use through the platform's native OpenTelemetry export without
   collecting full inputs or outputs.
7. Reapprove integrations periodically and revoke unused servers, scopes, and credentials.

For strict regulated environments, prefer a fixed approved server set or disable MCP entirely
until each integration has an approved threat model.

## Change governance

Every harness release should include:

- semantic version;
- release notes and migration notes;
- test evidence for allowed and denied hook cases;
- plugin validation evidence;
- compatibility statement for the supported Codex and Python versions;
- rollback instructions;
- named owner and exception process.

## Metrics

Track adoption and control effectiveness without collecting source code or prompts:

- repositories and developers on each harness version;
- hook denials by category, from each project's local `.codex/logs/hooks-audit.jsonl` (written by
  `log_event` in `.codex/hooks/_common.py`; one JSON line per deny/block decision with timestamp,
  hook name, category, decision, and tool name - never command text, file contents, or matched
  values). Aggregate this file centrally through your existing log pipeline; it is not collected
  automatically;
- false-positive and override rates;
- quality-gate duration and failure category;
- time to remediate secrets and vulnerable dependencies;
- percentage of projects with current lock files and documented data handling;
- MCP servers by owner, version, scope, and review expiry;
- OpenTelemetry-derived agent and tool-use metrics, kept to metadata.
