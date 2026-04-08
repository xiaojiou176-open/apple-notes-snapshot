# Apple Notes Snapshot Public Skills Pack

These files are the public-safe subset of the repo's internal skills.

What this pack is for:

- keeping public wording truthful
- keeping builder-facing docs aligned across CLI, AI Diagnose, Local Web API,
  and MCP
- giving repo-scoped workflows a reusable guidance layer without leaking
  internal task-board or archive assumptions

What this pack is not:

- a dump of `.agents/skills/`
- a maintainer closeout pack
- a proof that every host already has a native skill loader for these files

Tagged truth and update story:

- the public pack became tagged truth in `v0.1.7`
- current main may keep tightening the wording between tags
- host storage paths and approval steps still belong to the current host docs, not to this repo

What is newly public-safe in the current main branch:

- `runtime-resource-hygiene.md`
  - makes browser/profile/tab cleanup, Docker restraint, and branch/worktree/PR convergence part of the shareable repo-scoped guidance layer
  - keeps non-GitHub external control planes read-only by default
- `notes-snapshot-control-room/`
  - a standalone skill packet with its own `SKILL.md`
  - a repo-owned `manifest.yaml` that keeps ClawHub-style submit metadata next
    to the packet without claiming a live listing already exists
  - keeps the control-room identity, preflight-before-attach rule, and
    starter-pack versus official-listing boundary in one portable folder

Internal-only categories that stay out:

- task-board and archive-driven closeout guidance
- machine-path or machine-private operational detail
- manual-local validation ladders and evidence artifacts
- cross-repo leak-detection or maintainer-only review rituals

Public-safe inclusion test:

- keep a file in this pack only if it still works as repo-scoped guidance without private machine paths
- pull it back out if it starts depending on task-board state, owner-session-only actions, or maintainer-only closeout rituals
- keep OpenClaw-style front doors in comparison-only territory; do not treat that category as a plugin or runtime binding

Files:

- `repo-truthful-positioning.md`
  - protect the control-room-first product identity
- `agent-surfaces-contracts.md`
  - keep builder and agent entrypoints aligned
- `runtime-resource-hygiene.md`
  - keep browser/profile/tab cleanup, repo-owned Docker restraint, and branch/worktree/PR convergence explicit at repo scope
- `notes-snapshot-control-room/SKILL.md`
  - standalone public skill packet for repo-scoped host guidance or future
    skill-registry lanes
- `notes-snapshot-control-room/manifest.yaml`
  - repo-owned submit metadata for ClawHub-style listings and other skill-folder
    distribution lanes

Use these files as copyable repo-scoped guidance. Pair them with your host's
current docs for the exact storage path or registration UI.

If you need the runtime contract, pair this pack with:

- `docs/for-agents/index.html`
- `docs/for-agents/integration-pack/index.html`
- `docs/mcp/index.html`
- `docs/local-api/index.html`
