---
description: Preflight Apple Notes Snapshot before you attach MCP, Local Web API, or AI Diagnose to a local coding host.
argument-hint: [host-name]
allowed-tools: [Read, Glob, Grep, Bash]
---

# Apple Notes Snapshot Preflight

Use this command when you are about to wire Apple Notes Snapshot into Codex,
Claude Code, OpenClaw, or another local host.

## What to confirm first

1. You are inside the `apple-notes-snapshot` repository, or you have set
   `APPLE_NOTES_SNAPSHOT_REPO_ROOT` to that checkout.
2. The local snapshot loop has already completed at least one successful run.
3. `./notesctl verify` and `./notesctl doctor --json` are healthy before you
   call an attach failure.

## Minimum operator ladder

```bash
./notesctl run --no-status
./notesctl verify
./notesctl doctor --json
./notesctl status --json
```

## Truthful boundary

- This bundle is a project-scoped wiring kit.
- It does not prove named-host attach on every machine.
- It does not turn Apple Notes Snapshot into a hosted platform or official
  marketplace listing.

## If the user names a host

If the user mentions a host in `$ARGUMENTS`, remind them to use the
host-specific starter pack plus the post-attach checklist before they claim the
integration is done.
