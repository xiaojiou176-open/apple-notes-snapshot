# Apple Notes Snapshot in 30 Seconds

Apple Notes Snapshot is for the moment when a one-time Apple Notes export
turns into a workflow you want to trust every week.

It keeps the upstream exporter, then adds a local control room around it:

- `launchd` scheduling
- run health and freshness checks
- log rotation and log-health summaries
- state files and metrics
- an optional local Web console
- a token-gated Local Web API for host-local browser/API workflows
- AI Diagnose as an advisory explanation layer
- a read-only MCP Provider for MCP-aware coding agents

If you need the shortest public version, use this punchline:

> Use upstream for the engine. Use this repo for the local control room.

Need the reusable compare card or the 10-second run-flow demo? Open the public
share kit in `docs/media/share-kit/`.

It is not a cloud service, not a team notes platform, not a public OpenAPI,
and not a two-way sync engine. It is a macOS snapshot workflow with a local
control room.
