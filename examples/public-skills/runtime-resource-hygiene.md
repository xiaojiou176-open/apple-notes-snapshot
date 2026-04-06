# Runtime Resource Hygiene

## Purpose

Keep repo-scoped work from turning into shared-machine mess.

## When To Use It

Use this guidance when a repo task may:

- open browser automation sessions
- create temporary browser profiles or user-data directories
- create repo-owned Docker or temp-server residue
- finish with Git/GitHub branches, worktrees, or PRs that still need an explicit ending

## Core Rules

1. Treat browser ownership as explicit.
   - Only use sessions, tabs, or profiles you created for the current repo/task.
   - Do not borrow another repo's active browser session.

2. Keep the browser footprint small.
   - Prefer one owned window and the smallest possible tab count.
   - If the machine already has more than 6 Chrome/Chromium instances in play, do not add another one unless the task truly cannot be proven another way.
   - Prefer background / non-focus browser modes when your tooling supports them.
   - If you only need to confirm login state, try once or twice, classify the result, and stop reopening browsers.

3. Keep temporary profiles repo-scoped.
   - Put them under a path you can clean, such as `.runtime-cache/browser/<task-slug>/`.
   - Delete them when the task ends unless you have a live reason to preserve them.

4. Clean only what you own.
   - Stop repo-owned temp servers and remove repo-owned Docker residue.
   - Do not do blind machine-wide Docker cleanup on a shared workstation.

5. Keep external control planes read-only by default.
   - GitHub repo collaboration writes are the only standing exception when the current task explicitly includes branch / PR / review / merge / release closeout for this repo.
   - Search Console, registrars, DNS, video, social, and listing platforms stay read-only unless the user explicitly authorizes that exact write action.
   - Already-logged-in is not permission.

6. Finish Git/GitHub residue explicitly.
   - Task-owned branches, worktrees, and PRs should end as merged, salvaged then deleted, or closed with a clear reason.

## Success Check

- No task-owned stray tabs, temp profiles, or Docker residue remain.
- No task-owned stale branches/worktrees/PRs remain without an explicit verdict.
- External control planes stayed read-only unless the user explicitly approved a specific write action.
