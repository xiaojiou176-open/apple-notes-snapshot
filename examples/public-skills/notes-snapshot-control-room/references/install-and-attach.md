# Install And Attach

Use this reference when the agent or reviewer asks:

- how do I install the MCP lane?
- what exact command should the host run?
- what has to be proven before attach claims?

## Minimum operator proof

Before any host attach claim, prove the operator lane first:

```bash
./notesctl run --no-status
./notesctl install --minutes 30 --load
./notesctl verify
./notesctl doctor
```

If those commands fail, call it a local snapshot preflight problem, not an MCP
bug.

## MCP launch contract

The canonical MCP launch command is:

```bash
./notesctl mcp
```

For a generic MCP host that expects `command` plus `args`, use:

```json
{
  "mcpServers": {
    "apple-notes-snapshot": {
      "command": "/absolute/path/to/notesctl",
      "args": ["mcp"]
    }
  }
}
```

Replace `/absolute/path/to/notesctl` with the path for the local checkout.

## Builder surfaces that pair with this skill

- AI Diagnose: `./notesctl ai-diagnose`
- Local Web API: `./notesctl web`
- MCP Provider: `./notesctl mcp`

These three surfaces are not interchangeable:

- AI Diagnose = explanation layer
- Local Web API = token-gated same-machine browser/API lane
- MCP = read-only-first stdio host lane

## Capability boundary

This skill teaches local control-room attach and proof. It does **not** imply:

- a hosted runtime
- a Docker lane for the full product
- a universal attach proof on every machine
