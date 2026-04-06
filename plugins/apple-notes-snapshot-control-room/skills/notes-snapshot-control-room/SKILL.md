---
name: notes-snapshot-control-room
description: Use this skill when the user asks to connect Apple Notes Snapshot to Codex, Claude Code, OpenClaw, or another local coding host, or when they ask what this bundle does. Keep the product identity control-room-first, require local preflight before attach claims, and keep official-listing claims separate from repo-owned starter packs and local marketplaces.
version: 1.0.0
---

# Apple Notes Snapshot Control-Room Bundle

## Purpose

Help local coding hosts consume Apple Notes Snapshot without rewriting the
product story.

## Keep this identity first

- Apple Notes local-first backup control room for macOS
- `notesctl` is the canonical human entrypoint
- `AI Diagnose` is an advisory sidecar
- `Local Web API` is token-gated and same-machine
- `MCP` is stdio-first and read-only-first

## Preflight before any attach claim

Do not treat host registration as proof by itself.

Ask for or verify:

1. `./notesctl run --no-status`
2. `./notesctl verify`
3. `./notesctl doctor --json`
4. `./notesctl status --json`

If those fail, call it a local snapshot preflight problem, not an MCP bug.

## Truthful distribution boundary

- Repo-owned starter packs and local marketplaces are public-ready wiring kits.
- They are not the same thing as official public directory listing.
- Named-host attach proof still belongs to the host on the developer's machine.

## Best-fit use cases

- Project-scoped MCP setup for Codex or Claude Code
- OpenClaw MCP registry starting points
- Repo-scoped prompt or review workflows that must keep builder wording honest
