# Apple Notes Snapshot Control-Room Bundle

This directory is the repo-owned plugin-grade bundle for local coding hosts.

What it includes:

- `.claude-plugin/plugin.json`
- `.codex-plugin/plugin.json`
- `.mcp.json`
- a repo-root resolver script that launches `./notesctl mcp`
- one preflight command
- one public-safe skill

What it is for:

- a local Claude Code marketplace/plugin install path
- a Codex local plugin bundle and local marketplace surface
- a bundle-compatible starting point for OpenClaw, which documents support for
  `.claude-plugin/` and `.codex-plugin/` bundle layouts

What it is not:

- an official Codex directory listing
- an official Claude marketplace listing
- an OpenClaw marketplace or ClawHub listing
- a proof that attach already succeeded on every developer machine

## Install and verify

### Claude Code local marketplace proof

```bash
claude plugin validate /absolute/path/to/apple-notes-snapshot
claude plugin marketplace add /absolute/path/to/apple-notes-snapshot
claude plugin install apple-notes-snapshot-control-room@apple-notes-snapshot-local --scope project
claude plugin list --json
claude mcp add -s project apple-notes-snapshot -- /absolute/path/to/notesctl mcp
claude mcp list
```

### Codex live attach proof

```bash
codex mcp add apple-notes-snapshot -- /absolute/path/to/notesctl mcp
codex mcp list --json
codex mcp get apple-notes-snapshot --json
```

Codex's official plugin docs currently describe local plugins plus an official
directory where public third-party entries are still marked "coming soon". This
bundle gives you the local plugin-grade surface while keeping that boundary
honest.

### OpenClaw boundary

OpenClaw documents a real public registry/discovery route through ClawHub, but
this repository does not claim a published ClawHub package in this round. Use
the tracked OpenClaw starter pack and MCP registry payloads, and keep the final
attach proof on the OpenClaw host side.

## Update and remove

- Update this bundle by pulling the latest repo changes, then rerun `claude plugin validate`.
- Refresh Claude marketplaces with `claude plugin marketplace update apple-notes-snapshot-local`.
- Remove a local Claude install with `claude plugin uninstall apple-notes-snapshot-control-room`.
- Remove a direct Claude/Codex MCP registration with the host's `mcp remove` command.

## Resolver behavior

The bundled `scripts/notes_snapshot_mcp.sh` script looks for the real repo
checkout in this order:

1. `APPLE_NOTES_SNAPSHOT_REPO_ROOT`
2. `CLAUDE_PROJECT_DIR`
3. `CODEX_PROJECT_DIR`
4. the current working directory and its parents
5. `git rev-parse --show-toplevel`

If you install this bundle outside the repo and the host does not launch from
the project directory, set `APPLE_NOTES_SNAPSHOT_REPO_ROOT=/absolute/path/to/apple-notes-snapshot`
before you expect the bundle to start `notesctl mcp`.
