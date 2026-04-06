# Apple Notes Snapshot Integration Examples

These examples package the builder surfaces that the repository already ships
today.

What they assume first:

1. You reviewed `config/notes_snapshot.env`.
2. You ran `./notesctl run --no-status` at least once.
3. You ran `./notesctl verify` and `./notesctl doctor --json`.

What these examples are for:

- local stdio MCP registration
- same-machine Local Web API reads
- truthful host-side starting points for Codex, Claude Code, OpenCode, and OpenClaw
- comparison-only boundary setting for OpenHands and OpenClaw-style front-door positioning
- plugin-grade local marketplace and bundle surfaces for Codex and Claude Code
- post-attach verification on the same machine

What these examples are not:

- public OpenAPI or SDK examples
- hosted control-plane setup
- proof that every named host has been attach-verified in this repository
- proof that OpenHands has a dedicated first-party binding here
- proof that OpenClaw is a repo-owned front-door product binding instead of a host-side MCP path

Proof legend:

- `repo-side proven` = the repo itself verifies the underlying contract
- `attach-proven` = a named host attach was freshly proven on a real host session in this round, though other machines may still need local verification
- `host-side verify required` = the repo contract is ready, but the host still has to prove attach on your machine
- `template-only` = this repo gives you a starting file, not attach proof
- `comparison-only` = this repo mentions the host only to mark scope and avoid overclaiming

Files:

- `builder-contract.manifest.json` -> machine-readable inventory of the current builder surfaces, host proof levels, help entrypoints, and copyable assets
- `.claude-plugin/marketplace.json` -> local Claude Code marketplace surface for the repo-owned plugin bundle
- `.codex-plugin/marketplace.json` -> local Codex plugin marketplace surface for the repo-owned bundle
- `plugins/apple-notes-snapshot-control-room/README.md` -> install/update/remove notes for the repo-owned plugin-grade bundle
- `plugins/apple-notes-snapshot-control-room/.claude-plugin/plugin.json` -> Claude Code plugin manifest
- `plugins/apple-notes-snapshot-control-room/.codex-plugin/plugin.json` -> Codex plugin manifest
- `plugins/apple-notes-snapshot-control-room/.mcp.json` -> bundled MCP wiring that delegates to the repo-owned `notesctl mcp` path
- `codex-mcp-add.txt` -> one-line Codex MCP registration command
- `generic-stdio-mcp.json` -> host-agnostic stdio MCP launch shape
- `claude-project-mcp.json` -> project-scoped Claude Code MCP example
- `claude-user-mcp.json` -> user-scoped Claude Code MCP example
- `opencode.jsonc` -> OpenCode local MCP template; treat it as a template, not a proven attach result
- `openclaw-mcp.json` -> OpenClaw MCP registry payload for `notesctl mcp`
- `openclaw-mcp-set.txt` -> one-line OpenClaw MCP registration command
- `local-web-api.env.example` -> loopback-first Local Web API environment values
- `local-web-api.curl.sh` -> minimal same-machine read calls
- `post-attach-checklist.md` -> repo-owned checklist for proving the attach worked on your host

For the host matrix, exact help entrypoints, and capability table, open:

- `docs/for-agents/integration-pack/index.html`
- `examples/integration-pack/builder-contract.manifest.json`
- `docs/for-agents/openclaw-starter-pack/index.html`
- `plugins/apple-notes-snapshot-control-room/README.md`
