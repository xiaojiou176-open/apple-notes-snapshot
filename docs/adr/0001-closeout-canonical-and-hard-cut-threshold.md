# ADR 0001: Canonical Closeout Truth And Hard-Cut Promotion Threshold

- Status: Accepted
- Date: 2026-04-06

## Context

Apple Notes Snapshot is a local-first wrapper around a vendored upstream engine.
The repository currently ships a CLI contract, a token-gated local Web API, a
read-only MCP surface, and public documentation, but it does **not** ship a
public OpenAPI, generated SDK, or public schema package.

Closeout work for this repository also crosses multiple truth layers:

- tracked tree truth
- Git history truth
- GitHub control-plane truth
- live public release and Pages truth

Historically, those layers can drift. A clean working tree is not enough to
declare the repository closed clean, and a historical "done" claim is not live
truth.

## Decision

We use the following closeout policy:

1. Preserve code before cleanup, rewrite, or cutover.
2. Record a truth anchor before destructive Git or GitHub actions.
3. Treat the current tracked tree as canonical repo-side truth unless fresh
   evidence proves historical contamination or platform residue requires a
   stronger response.
4. Keep hard cut (`history rewrite + new canonical repo`) as a **first-class**
   route, not a fallback of last resort.
5. Promote from in-place closeout to hard cut when any of these become true:
   - Git history scans find real leaked secrets or real machine-private paths.
   - GitHub raw/source/search surfaces still expose stale polluted content.
   - Reconstructing a reviewable public history in-place is riskier than a new
     clean canonical repo.
   - Canonical repo identity, release surface, and public entry need a single
     controlled cutover.
6. Do not create fake API or schema contracts just to satisfy a generic docs
   tree. This repository's truthful public contracts remain:
   - `notesctl`
   - the token-gated local Web API
   - the read-only MCP surface
   - current public docs and release notes

## Consequences

- Maintainers must keep `repo-side engineering`, `delivery landed`,
  `git closure`, and `external blocker` as separate ledgers.
- Releases must point at the current canonical closeout commit.
- GitHub control-plane settings such as required checks, vulnerability alerts,
  and Pages remain live settings that need fresh verification.
- Hard-cut migration remains available whenever the promotion gate says it is
  the safer, more truthful path.
