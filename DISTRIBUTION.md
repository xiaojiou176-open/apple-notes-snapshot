# Distribution Surface

This file is the exact claim boundary for Apple Notes Snapshot's distribution
story.

Treat it like a shipping ledger, not like the repo's front-door sentence. The
front door still starts with `Run -> Install -> Verify`, then opens deeper
builder or listing lanes only after that first healthy local loop exists.

Use this file when you need to answer:

- which repo-owned distribution artifacts are canonical
- which public listings are live today
- which lanes are still external-only or review-pending
- how the MCP descriptor, `.mcpb` package, and public-skill packet converge

## Public Distribution Matrix

| Surface | Repo-owned artifact shipped | Current truthful boundary |
| --- | --- | --- |
| Official MCP Registry descriptor | `server.json` | the repo ships the canonical stdio-first MCP descriptor for `io.github.xiaojiou176-open/apple-notes-snapshot`; keep the product story local-first instead of registry-first |
| Release `.mcpb` companion package | `packaging/mcpb/manifest.json` | the `.mcpb` package is companion packaging around the same `notesctl mcp` workflow, not a separate hosted product |
| Public standalone skill packet | `examples/public-skills/notes-snapshot-control-room/manifest.yaml` | the public skill packet is repo-owned and listing-ready; ClawHub is live today for this packet lane |
| Goose Skills Marketplace | `examples/public-skills/notes-snapshot-control-room/manifest.yaml` | the public skill packet is submitted on [`block/Agent-Skills#27`](https://github.com/block/Agent-Skills/pull/27); keep this lane at review-pending until maintainers accept it |
| agent-skill.co source repo | `examples/public-skills/notes-snapshot-control-room/manifest.yaml` | the public packet is submitted to the community index on [`heilcheng/awesome-agent-skills#183`](https://github.com/heilcheng/awesome-agent-skills/pull/183); directory acceptance is still pending |
| OpenHands/extensions skill lane | `examples/public-skills/notes-snapshot-control-room/manifest.yaml` | the packet is submitted, changes requested, and not accepted or listed live yet; treat this as external-only review tail, not a repo blocker |

## Canonical Repo-Owned Artifacts

- `server.json`
- `packaging/mcpb/manifest.json`
- `examples/public-skills/notes-snapshot-control-room/manifest.yaml`

These three files describe the same control-room distribution story from three
angles:

- `server.json` is the MCP descriptor/read-back lane
- `packaging/mcpb/manifest.json` is the companion `.mcpb` packaging lane
- `examples/public-skills/notes-snapshot-control-room/manifest.yaml` is the
  public skill-folder listing lane

## Live And External-Only Boundaries

This section is the current `external-only / review-pending` split.

- **Live today**
  - official MCP Registry descriptor/read-back for
    `io.github.xiaojiou176-open/apple-notes-snapshot`
  - ClawHub is live today for `notes-snapshot-control-room`
- **External-only / review-pending**
  - Goose Skills Marketplace PR `block/Agent-Skills#27` is open and blocked on
    external maintainer review
  - community index PR `heilcheng/awesome-agent-skills#183` is open and still
    waiting on external acceptance
  - OpenHands/extensions `#150` remains submitted with changes requested and is
    not accepted or listed live

## Allowed Claims

- "`server.json` is the canonical MCP descriptor for Apple Notes Snapshot"
- "the release `.mcpb` package is companion packaging around the same local
  control-room workflow"
- "the standalone public skill packet ships repo-owned listing metadata"
- "ClawHub is live today for the public skill packet"
- "Goose Skills Marketplace submission is review-pending on `block/Agent-Skills#27`"
- "the community index submission is review-pending on `heilcheng/awesome-agent-skills#183`"

## Forbidden Claims

- "Run -> Install -> Verify is no longer the front door"
- "the `.mcpb` package proves a hosted runtime"
- "Goose Skills Marketplace is listed live" without fresh accepted read-back
- "agent-skill.co is live" without fresh accepted read-back
- "OpenHands/extensions is live" without fresh accepted read-back
- "official listing everywhere" or "universal attach proof on every machine"
