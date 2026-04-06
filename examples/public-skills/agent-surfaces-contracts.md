# Agent Surfaces Contracts

## Purpose

Keep all builder-facing and agent-facing entrypoints aligned so readers can tell
what each surface does, what it does not do, and how it maps back to the
repo-owned control room.

## When To Use It

Use this guidance when changing:

- `docs/for-agents/*`
- `docs/mcp/*`
- `docs/local-api/*`
- `docs/ai-diagnose/*`
- builder or agent sections in the README
- related release or discovery wording

## Contract To Preserve

- `CLI`
  - deterministic control-room entrypoint
- `AI Diagnose`
  - advisory sidecar over structured operational state
  - not the system of record
- `Local Web API`
  - token-gated, same-machine browser and HTTP lane
  - not a public hosted API
- `MCP`
  - read-only-first, stdio-first agent substrate
  - backed by repo-owned state and `notesctl`

## Editing Rules

1. Start from the control-room identity, not from the agent surface.
2. Explain each surface by scope, access boundary, and backing implementation.
3. Keep AI Diagnose opt-in and advisory.
4. Keep Local Web API distinct from public OpenAPI claims.
5. Keep MCP described as read-only-first and stdio-first unless the repo truly proves more.
6. When one surface changes, check the linked surfaces for drift.

## Guardrails

- Do not present Local Web API as public OpenAPI or hosted API unless that truly exists.
- Do not present MCP as write-capable by default.
- Do not present MCP as remote HTTP unless that contract truly landed.
- Do not let AI Diagnose drift into note-content analysis if the real contract is structured operational state.
- Do not let Codex or Claude wording outrun actual builder utility.

## Success Check

- A reader can distinguish CLI vs AI Diagnose vs Local Web API vs MCP in one pass.
- The access boundary is clear for every surface.
- Builder-facing docs do not contradict each other.
- The repo remains discoverable without overclaiming platform scope.
