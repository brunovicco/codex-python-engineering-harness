# Architecture decisions

## Codex-native surfaces

- `AGENTS.md` is the durable repository contract; generated profile overlays replace it only when
  their commands and layout differ.
- Project skills live in `template/.agents/skills/`; distributable copies live at the plugin root
  under `skills/`.
- Generated projects use `.codex/config.toml` for portable trusted-project settings and a sibling
  `.codex/hooks.json` as the only hook representation at that layer.
- Hook scripts stay in `.codex/hooks/` so commands can resolve them from the Git root when Codex
  starts in a subdirectory.
- The plugin uses the documented default `hooks/hooks.json`; its commands resolve scripts through
  `PLUGIN_ROOT` and its manifest does not duplicate the default hook path.
- The repo marketplace is `.agents/plugins/marketplace.json` and points to `./plugins/...` relative
  to the marketplace root.

## Profile composition

`template/` is the service-compatible base. `library` removes service/container/observability
pieces and overlays library metadata. `workspace` removes all artificial package/test trees and
overlays a virtual uv root. Profiles are generator choices, never monorepo packages in this repo.

## Governance composition

Technical profiles and governance are orthogonal. `--governance-profile` selects capability-based
controls while repeatable `--governance-overlay` options add regulatory requirements. `none` is the
default to keep upgrades compatible. The bootstrap snapshots the canonical catalog, schemas, and
composed selection into each governed project; generated projects never depend on this source
repository at runtime.

The catalog uses original control descriptions and many-to-many support mappings. It does not copy
licensed standards or assert compliance. Project-owned inventories, risks, assessments, and
exceptions remain separate from bootstrap-owned snapshots.

## Controls

Lifecycle hooks provide defense in depth for command safety, sensitive paths, secret scanning,
MCP mutation classification, and changed-file formatting. They do not replace Codex sandboxing,
approvals, hook trust, CI, or human review. Native command execution rules were not added because
there is no concrete project command exception to encode; prose conventions belong in
`AGENTS.md`, while command-policy rules should be introduced only for an evidenced need.

MCP configuration moved from a tool-specific JSON schema to native `[mcp_servers.*]` TOML. The
validator enforces TLS, environment-name credential indirection, exact ephemeral-runner versions,
direct STDIO commands, and bounded timeouts.
