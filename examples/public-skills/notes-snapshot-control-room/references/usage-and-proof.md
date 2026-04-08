# Usage And Proof

Use this reference when the reviewer asks:

- what does the skill help an agent do in practice?
- where is the public proof?
- how do I test it without guessing?

## First-success path

The shortest truthful path is:

```bash
./notesctl run --no-status
./notesctl install --minutes 30 --load
./notesctl verify
./notesctl doctor
./notesctl status --full
```

Then, if the local state exists, move into builder surfaces:

```bash
./notesctl ai-diagnose
./notesctl web
./notesctl mcp
```

## Example prompts

- "Is this Apple Notes Snapshot problem a local preflight failure or an MCP attach failure?"
- "Explain the current backup loop status using the control-room proof path."
- "Walk me from operator proof to builder attach without overstating what is officially listed."
- "Which surface should I use here: AI Diagnose, Local Web API, or MCP?"

## Proof / demo links

- Landing: https://xiaojiou176-open.github.io/apple-notes-snapshot/
- Quickstart: https://xiaojiou176-open.github.io/apple-notes-snapshot/quickstart/
- Proof page: https://xiaojiou176-open.github.io/apple-notes-snapshot/proof/
- MCP provider guide: https://xiaojiou176-open.github.io/apple-notes-snapshot/mcp/
- For Agents overview: https://xiaojiou176-open.github.io/apple-notes-snapshot/for-agents/
- Public skills pack docs: https://xiaojiou176-open.github.io/apple-notes-snapshot/for-agents/public-skills/

## Reviewer one-liner

If the reviewer asks "what does this skill teach?", answer:

> It teaches an agent how to prove Apple Notes Snapshot's local control room,
> wire the `notesctl mcp` lane, and separate repo proof, host proof, AI
> Diagnose, Local Web API, and MCP into honest boundaries.
