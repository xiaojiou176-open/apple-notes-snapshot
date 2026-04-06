# Why Apple Notes Snapshot Exists

Exporting notes once is not the hard part.

The hard part is returning to a local workflow weeks later and still knowing:

- whether it ran
- when it last succeeded
- why it failed
- whether the scheduler is still pointed at the right checkout
- whether the logs are saying something important

Apple Notes Snapshot exists to make that second problem boring.

It keeps the upstream exporter doing the actual extraction work, then adds a
small, reviewable operations layer so the workflow stays visible and easier to
recover when the local environment changes.

That operations layer now includes three truthful optional surfaces on top of
the same local substrate:

- AI Diagnose for calmer operator explanations
- Local Web API for token-gated same-machine browser/API reads
- MCP Provider for read-only agent access

The shortest public version is:

> Use upstream for the engine. Use this repo for the local control room.
