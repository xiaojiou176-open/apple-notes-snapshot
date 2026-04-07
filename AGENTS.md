# Apple Notes Snapshot Agent Guide

This repository is a local-first Apple Notes export wrapper for macOS.

## Mission

Keep the repository reviewable, path-safe, and open-source friendly.

## Rules

- Keep changes surgical.
- Prefer fixing repo-owned wrapper code over editing vendored upstream code.
- Keep all repo-owned documentation in English.
- Never let real secrets, tokens, session material, personal email addresses,
  or live diagnostic residue enter the tracked tree, Git history, release
  notes, screenshots, fixtures, or public docs.
- Prefer placeholder paths such as `${HOME}/...`, `/path/to/...`, or
  `<local-reference-root>/...` in docs, fixtures, and examples instead of real
  machine-specific absolute paths.
- Treat any dirty worktree as meaningful until proven otherwise; preserve code
  before cleanup, rewrite, branch deletion, or remote cutover.
- Before destructive Git or GitHub actions, record a truth anchor and create a
  rollback asset such as a bundle, backup branch, or equivalent snapshot.
- Never track `.agents/`, `.agent/`, `.codex/`, `.claude/`, `.serena/`, `.runtime-cache/`,
  `generated/launchd/`, `logs/`, or runtime log files.
- `AGENTS.md` and `CLAUDE.md` may be tracked when they are part of the public
  repository contract.
- Keep `current tracked tree`, `Git history`, and `GitHub control-plane`
  statements separate.

## Execution hygiene

- Treat browser sessions, cloned browser profiles, Docker containers, and caches
  as scarce shared machine resources, not disposable scratch space.
- Treat `.serena/` as a local MCP/shared-tool cache surface. Keep it ignored and
  out of repo-owned janitor governance.
- Treat the repo-managed isolated Chrome root as persistent runtime state for
  this repo. It is excluded from TTL/cap janitor cleanup.
- Before using Chrome / Chromium, inventory the current machine state first:
  task-owned windows, tabs, and temporary profiles must be attributable to this
  task.
- If the machine already has more than 6 Chrome/Chromium instances in play, do
  not open another one. Prefer non-browser evidence paths, wait for cleanup, or
  use a non-Chrome path that you can keep isolated and short-lived.
- Treat `6` as the hard shared-machine cap. Within that cap, still prefer one
  task-owned browser session when the current proof does not require more.
- Do not open or reuse Chrome / Chromium / browser instances that belong to a
  different repo or another active L1 worker on the same machine.
- Prefer one task-owned browser session at a time; close extra tabs, windows,
  and temporary profiles as soon as the current proof is captured.
- If a task requires a temporary browser profile, record the path, keep it
  repo-scoped under `.runtime-cache/browser/<task-slug>/`, and delete it when
  the task ends.
- A single task should default to one task-owned browser instance and the
  smallest possible number of tabs.
- If the task only needs to confirm login state, do not keep reopening browser
  instances. Try once or twice, classify the state, and move on.
- If the browser tooling supports background or non-focus execution, prefer it
  so the task does not steal focus from other active work on the shared
  machine.
- Do not leave repo-owned Docker containers, images, or caches running unless
  the current task still actively needs them.
- If a task starts Docker/compose/temp-server resources, those resources must
  be identifiable as repo-owned and must be removed before closeout unless an
  explicit preserved reason is recorded.
- Every task-owned branch, worktree, and PR must end in one of three states:
  merged to `main`, salvaged to `main` then deleted, or closed/deleted as
  confirmed no-value residue.
- GitHub repo collaboration writes are allowed only when the task explicitly
  includes branch / PR / review / merge / release closeout for this repo.
- Every non-GitHub external control plane stays read-only by default. Do not
  perform write actions against Search Console, registrars, social platforms,
  video platforms, or other outside accounts unless the user explicitly
  re-authorizes that exact write action in the current conversation.

## Verification

Use the repo-owned environment:

```bash
./notesctl rebuild-dev-env
./.runtime-cache/dev/venv/bin/python -m pre_commit run --all-files
PYTHON_BIN=./.runtime-cache/dev/venv/bin/python scripts/checks/ci_gate.sh
scripts/checks/actionlint_gate.sh
scripts/checks/zizmor_gate.sh
TRIVY_BIN=/path/to/trivy scripts/checks/trivy_fs_gate.sh
```

Maintainer verification expects Python 3.11+ and a fresh repo-owned virtual
environment. `./notesctl rebuild-dev-env` is responsible for recreating
`.runtime-cache/dev/venv` before the other verification commands run.

Keep the verification layers separate:

- `pre-commit` = quick hygiene only
- `pre-push` = deterministic repo-local quick gate only
- `hosted` = GitHub Actions / GitHub-state-aware security and policy gates
- `nightly` = intentionally unused until a deterministic deep audit truly needs it
- `manual` = real-machine / owner-session proof such as browser, desktop, provider, or external control-plane checks

## Boundaries

- `notesctl` is the canonical human entry point.
- `config/notes_snapshot.env` is the runtime configuration surface.
- `vendor/notes-exporter/` is treated as generated upstream content.
