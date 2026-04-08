# Contributing

## Scope

This repository is a local-first Apple Notes snapshot/export utility for macOS.
The best contributions are small, reviewable, and easy to verify.

Good contribution areas:

- migration and path robustness
- launchd and log handling
- onboarding clarity
- safer defaults for local automation
- test coverage for repo-owned wrapper logic

## Development Setup

Use the repo-owned rebuild command if you want a path-aware local test
environment that can be regenerated after the checkout path changes:

```bash
./notesctl rebuild-dev-env
```

Maintainer verification expects a local Python 3.11+ toolchain. The rebuild
command recreates `.runtime-cache/dev/venv` from scratch so stale interpreter
links do not leak across path moves or Python upgrades.
GitHub Actions for this repo run on **GitHub-hosted runners**; local commands
here are maintainer verification, not a self-hosted runner policy.

Install the repo-managed hooks after Python tooling is available:

```bash
./.runtime-cache/dev/venv/bin/python -m pip install -r requirements-dev.txt
./.runtime-cache/dev/venv/bin/python -m pre_commit install --hook-type pre-commit --hook-type pre-push
```

Useful checks:

```bash
./notesctl doctor --json
./.runtime-cache/dev/venv/bin/python -m pre_commit run --all-files
PYTHON_BIN=./.runtime-cache/dev/venv/bin/python scripts/checks/ci_gate.sh
PYTHON_BIN=./.runtime-cache/dev/venv/bin/python scripts/checks/run_wrapper_smoke.sh
./.runtime-cache/dev/venv/bin/pytest tests/e2e --no-cov
```

## Testing Strategy

Treat the repo-owned verification stack as a small testing pyramid:

1. **Unit tests**
   - fastest protection for repo-owned Python logic, report shaping, and JSON contracts
   - examples:
     - `tests/unit/test_ai_diagnose_unit.py`
     - `tests/unit/test_mcp_server_unit.py`
     - `tests/unit/test_web_server_unit.py`
2. **Wrapper smoke**
   - shell-contract checks for `notesctl` help, JSON surfaces, and wrapper entrypoints
   - command:
     - `PYTHON_BIN=./.runtime-cache/dev/venv/bin/python bash scripts/checks/run_wrapper_smoke.sh`
3. **E2E**
   - slower integration checks for launchd, relocation, Web behavior, and repo-owned runtime flows
   - command:
     - `./.runtime-cache/dev/venv/bin/pytest tests/e2e --no-cov`
4. **Manual-local validation**
   - the real operator path on a real Mac:
     - `./notesctl run --no-status`
     - `./notesctl verify`
     - `./notesctl status --full`
     - `./notesctl doctor --json`
     - optional Web validation with a real token

The 90%+ coverage bar applies to repo-owned Python surfaces under `scripts/ops`.
Do not pretend the shell wrapper surface should be measured by the same metric;
that layer is protected by smoke and E2E coverage instead.

## Local Cleanup Contract

Use the repo-owned cleanup lane when you want to reclaim local rebuildables
without touching exported notes or tracked/public proof assets:

```bash
./notesctl clean-cache --dry-run
./notesctl clean-cache
./notesctl rebuild-dev-env
```

Treat this as a maintainer-only cleanup lane.
It is not part of the first-run path for recording the first successful
snapshot.

Current cleanup classes:

- `.venv/` and `.runtime-cache/dev/venv` -> rebuildable developer environments
- `.runtime-cache/cache/apple-notes-snapshot` -> repo-local runtime cache
- `.runtime-cache/temp` -> scratch
- `.runtime-cache/logs`, `.runtime-cache/pytest`, `.runtime-cache/coverage`, and `.runtime-cache/pycache` -> repo-local disposable/generated support surfaces
- `.runtime-cache/browser-proof` -> generated proof screenshots that can be recaptured
- `.runtime-cache/phase1` and `.runtime-cache/phase1-history-rebuild` -> historical rollback artifacts you can remove once you no longer need old cutover safety copies
- `.runtime-cache/mcp-registry-lane/out` -> rebuildable MCP registry lane artifacts
- legacy `.pytest_cache`, `.coverage`, and scattered `__pycache__` -> migration-only cleanup backstops if they still exist

External repo-owned residue belongs under the current repo-managed machine cache
root selected by the local cache-home contract. That root holds launchd state,
runtime mirrors, repo copies, browser state, and vendor-runtime scratch. Use:

```bash
./notesctl runtime-audit
./notesctl clean-runtime --dry-run
./notesctl browser-bootstrap
./notesctl browser-open
./notesctl browser-contract
```

The repo-owned janitor may clean that external root automatically on
`run`, `web`, `install`, `ensure`, `rebuild-dev-env`, and `runtime-audit`
using the default TTL and budget contract. It does not touch shared tool caches, Docker, or
system temp roots.

Browser-specific rule:

- the repo-managed isolated browser root is persistent runtime state
- the disposable browser temp root is the cleanup-eligible subtree
- only `browser/tmp/` is eligible for TTL/cap cleanup
- automation and manual work should attach to the same repo-owned Chrome instance over CDP instead of second-launching the same root
- `browser-bootstrap` is a one-time migration step; after you add or refresh logins inside the isolated root, do not rerun it unless you intentionally want to replace that isolated root from the default Chrome root again
- the default CDP port is `9337`; if that port is already occupied on your machine, use an explicit env override such as `NOTES_SNAPSHOT_CHROME_CDP_PORT=9347`

This repository has no repo-owned Docker cleanup contract today. Cleanup here
only covers local Python/tooling support surfaces.

## Change Rules

- Keep changes surgical.
- Prefer repo-owned wrapper fixes over ad hoc workarounds.
- Do not hardcode machine-specific absolute paths.
- Keep repo-local rebuildables under `.runtime-cache/` and repo-external
  repo-owned residue under the repo-managed machine cache root.
- Keep root documentation aligned with behavior in the same change set.
- Keep repo-owned documentation in English only.
- Do not commit personal notes, exported content, or secrets.
- Do not track `.agents/`, `.agent/`, `.codex/`, `.claude/`, `.serena/`, `.runtime-cache/`,
  `generated/launchd/`, `logs/`, or runtime log files.

## Security And Vendor Rules

- Follow `SECURITY.md` for vulnerability handling. Do not post exploit details,
  sample notes, tokens, or private paths in public issues.
- Treat the repo-managed hooks as the first safety net: pre-commit runs
  `gitleaks` plus repo-surface hygiene checks, and pre-push runs the canonical
  quick gate plus GitHub open-alert verification in `scripts/checks/ci_gate.sh`.
- GitHub Actions for this repo run on GitHub-hosted runners. The local
  verification ladder is for maintainer reproduction, not a self-hosted runner
  requirement.
- GitHub Secret Scanning and private vulnerability reporting are remote
  repository settings. Keep the local hooks green, but do not assume a local
  checkout can prove those GitHub-side controls are enabled.
- Keep `current tracked tree`, `Git history`, and `GitHub control-plane`
  statements separate when talking about path hygiene, secrets, or required
  checks.
- Use `.github/REPOSITORY_SETTINGS_CHECKLIST.md` when a release or governance
  change needs a manual GitHub-side settings review.
- Treat `vendor/notes-exporter/` as generated content. If upstream behavior
  must change, update `NOTES_SNAPSHOT_VENDOR_URL` and
  `NOTES_SNAPSHOT_VENDOR_REF`, then rerun `./notesctl update-vendor` instead of
  hand-editing the vendor tree.
- A vendor refresh is only reviewable when the regenerated
  `vendor/notes-exporter/VENDOR_INFO` records `source`, requested `ref`,
  resolved `commit`, and patch metadata without `unknown`.
- Governance-facing repository flow expects `.github/CODEOWNERS` and
  `.github/PULL_REQUEST_TEMPLATE.md` to stay committed alongside the existing
  workflow and security-contact template.

## Pull Request Notes

Please include:

- what changed
- why it changed
- how you verified it
- any macOS-specific assumptions or limitations

## Public Release Notes

When you prepare a public release, keep the repo-side artifacts aligned:

- update `CHANGELOG.md` as the canonical repo-side release history
- use `.github/RELEASE_TEMPLATE.md` as the checklist when you write the GitHub
  release body
- touch `docs/releases/` only when the release router or archival summaries need
  navigation cleanup; do not treat it as the canonical source of per-release facts

Public release notes should answer:

- why this matters
- what changed for first-time visitors
- upgrade / migration or rollback notes
- known limitations
- which docs / support links to open next

## Community Standards

- Follow `CODE_OF_CONDUCT.md` in all public and private project interactions.
- Use the repository issue templates for bug reports, feature requests, and
  security contact requests so the required context is captured consistently.
- Route setup help and usage questions through `SUPPORT.md` / Discussions before
  opening a bug issue.
