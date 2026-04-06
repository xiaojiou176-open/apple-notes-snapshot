# Repo Truthful Positioning

## Purpose

Keep this repository described as what it actually is: a local-first Apple
Notes backup control room for macOS, with AI and agent-facing features treated
as supporting layers instead of the primary product identity.

## When To Use It

Use this guidance when you touch:

- README wording
- docs front door, compare, roadmap, support, community, release, or discovery pages
- AI / MCP / Local Web API positioning
- builder-facing entrypoints

## Core Rules

1. State the primary identity first.
   - The repo is a local-first Apple Notes backup control room.
   - It is not an AI-first notes assistant.
   - It is not a hosted platform.
   - It is not a public API platform by default.

2. Keep the capability order stable.
   - control-room product truth first
   - AI Diagnose after the operator surface is clear
   - Local Web API as a token-gated same-machine lane
   - MCP as a read-only-first agent substrate
   - naming or discoverability experiments only after real capability lands

3. Keep growth wording downstream of real capability.
   - Improve findability for what already exists.
   - Do not rename the product around speculative AI traffic.
   - Do not promote aliases or rebrands into the primary identity unless they truly landed.

4. Sync every public surface that explains the same capability.
   - README
   - public docs
   - help text
   - release wording when relevant

## Guardrails

- Do not describe Local Web API as a hosted API unless that contract truly exists.
- Do not describe MCP as a remote agent platform when the real contract is local and read-only-first.
- Do not let AI or MCP wording overtake the control-room identity.
- Do not describe planning ideas as shipped brand decisions.

## Success Check

- A new reader understands the backup control room before the AI or MCP story.
- Public pages agree on the same capability order.
- No wording implies hosted, public, or platform scope that the repo does not prove.
