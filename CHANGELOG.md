# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

### Note

- no current main-only changes since `v0.1.12` yet

## [v0.1.12] - 2026-04-06

### Added

- a standalone public skill packet for `notes-snapshot-control-room` under
  `examples/public-skills/notes-snapshot-control-room/`
- an MCP Registry-ready lane with a tracked `server.json`, MCPB manifest,
  local build script, and artifact metadata output
- a registry-lane unit test that locks the public skill packet and MCPB release
  path into the repo contract

### Changed

- promoted Codex and OpenClaw from wiring-kit-only documentation to a tagged
  v0.1.12 attach-proof trail while keeping “other machine” verification separate
- aligned the last drifted support and security routing surfaces back to the
  current live `xiaojiou176-open` public identity
- expanded the public-skills surface so the control-room guidance can travel as
  a standalone packet instead of only as a plugin-embedded skill

### Fixed

- removed hand-copied MCP Registry hash drift by making the MCPB build script
  rewrite `server.json` after each fresh pack
- fixed the builder-manifest test contract so it matches the current named-host
  proof level

## [v0.1.11] - 2026-04-06

### Changed

- deepened the public-surface rhythm across Compare, Support, Community, Troubleshooting, Security, and Proof so the side rooms now read like the same exhibition as the front door
- tightened side-room navigation so operator-first routes stay clearer before builder or secondary surfaces
- separated support-desk, discussion-hall, troubleshooting-runbook, and proof-ledger roles more cleanly across the docs site

### Fixed

- release-truth drift after `v0.1.10`, so `CHANGELOG`, release history, proof, HTML release notes, and the latest public tag all point back at the same current truth

## [v0.1.10] - 2026-04-06

### Added

- second-pass curation polish across Home, Proof, For Agents, Releases, and Quickstart
- stronger visual signaling for proof ledgers, release storytelling, and builder-lane sequencing

### Changed

- deepened the public-surface storytelling so control-room, proof, and builder shelves now read more like a curated exhibit than a flat docs stack
- sharpened the visual language for curation cards, signal cards, and release-timeline highlights without changing product truth

### Fixed

- the gap where the second-pass curation polish had landed on `main` but was not yet part of the latest tagged public release

## [v0.1.9] - 2026-04-06

### Added

- a public proof page that concentrates repo-side gates, GitHub-controlled delivery evidence, and the same-machine live boundary
- HTML and markdown release notes for both the `v0.1.8` hard-cut baseline and this `v0.1.9` proof/front-door sync release
- extracted helper modules for AI Diagnose reporting, Web policy/static routing, and status rendering

### Changed

- reordered the README and docs front door so the control-room operator path comes first and builder surfaces sit clearly in the second lane
- synced release history, sitemap, and public proof/release narrative around the current tagged truth
- hardened launchd runtime cleanup so stale runtime-copy directories do not make `install --load` brittle

### Fixed

- release-history and changelog drift after the `v0.1.8` public hard cut
- the launchd runtime copy cleanup path that could fail with transient `Directory not empty` errors during `install --load`

## [v0.1.8] - 2026-04-06

### Added

- a hard-cut canonical public release for `xiaojiou176-open/apple-notes-snapshot`
- a public governance and closeout layer across `AGENTS.md`,
  `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md`, and
  `docs/runbooks/final-closeout.md`

### Changed

- retargeted the public repo, Pages, and release narrative to the rebuilt
  `xiaojiou176-open` baseline
- kept the control-room-first product identity while preserving AI Diagnose,
  Local Web API, MCP, and builder-facing surfaces as additive layers
- kept the verification and workflow guardrails intact on the rebuilt public
  repo baseline

### Fixed

- stopped older public release/docs assumptions from masquerading as the new
  canonical public-repo truth

## [v0.1.7] - 2026-04-03

### Added

- dedicated Codex and Claude Code starter-pack pages under `docs/for-agents/`
- a tracked public-skills pack under `docs/for-agents/public-skills/` and
  `examples/public-skills/`

### Changed

- linked the new starter-pack and public-skills surfaces across README, Home,
  `For Agents`, and the Builder Integration Pack
- split GitHub-controlled release and announcement work from external-only
  Search Console, domain, video, and social actions in the external launch prep
  packet
- rewrote the release-history current-main section so it no longer implies that
  `main` must always equal the latest public tag

### Fixed

- kept new starter-pack and public-skills surfaces inside the existing truthful
  host-proof boundary instead of overstating attach-verified support

## [v0.1.5] - 2026-03-25

### Added

- example-workflow docs in `docs/examples/`
- troubleshooting docs in `docs/troubleshooting/`

### Changed

- linked the landing page, support page, community page, and roadmap into the new examples and troubleshooting surfaces

## [v0.1.4] - 2026-03-25

### Added

- a public roadmap page in `docs/roadmap/`
- dedicated `v0.1.4` release notes for the roadmap and stale-link cleanup pass

### Changed

- linked the landing page into roadmap and release-history entry points
- replaced stale version-specific announcement and release links with longer-lived destinations

## [v0.1.3] - 2026-03-25

### Added

- a root `SUPPORT.md` file for issue and discussion routing
- a public support page in `docs/support/`
- richer issue-routing contact links plus curated support / launchd / needs-repro labels

### Changed

- disabled blank issues so visitors are routed through templates or discussion/support entry points
- updated the bug-report form to redirect setup and usage questions toward Q&A
- linked the README, docs home, community page, and contributing guide to the support surface

## [v0.1.2] - 2026-03-25

### Added

- a public community hub page in `docs/community/`
- a release history page in `docs/releases/index.html`
- changelog-backed release navigation across the public docs surface

### Changed

- linked the landing page to community and release-history entry points
- promoted the changelog from a one-shot launch note into a multi-version public history

## [v0.1.1] - 2026-03-25

### Added

- a public `.well-known/security.txt` endpoint for the Pages site
- a General "Start here" discussion for first-time visitors
- dedicated `v0.1.1` release notes for the post-launch discovery hardening pass

### Changed

- linked the Pages security summary to the public `security.txt` endpoint

## [v0.1.0] - 2026-03-25

### Added

- a conversion-focused README that presents the project as a local snapshot
  control room instead of a maintainer-only wrapper guide
- a GitHub Pages documentation surface in `docs/` with landing, quickstart,
  compare, FAQ, and security pages
- README and documentation visual assets for hero, comparison, architecture,
  run flow, and social sharing
- a Pages deployment workflow for publishing the `docs/` site from GitHub
  Actions
- release-ready media and notes for the first public launch bundle

### Changed

- restored `docs/` as a tracked public documentation surface for search and
  onboarding
- hardened ignore and hygiene rules for AI, runtime, generated, and log surfaces
- updated repo-surface checks so the public site surface is allowed, tracked,
  and still English-only

### Fixed

- stale references to the old root-only documentation contract
