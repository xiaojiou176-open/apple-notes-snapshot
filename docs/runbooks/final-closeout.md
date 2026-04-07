# Final Closeout Runbook

This runbook is the maintainer checklist for declaring Apple Notes Snapshot
closed clean or for promoting the repository into a hard-cut migration.

## 1. Preserve Before You Change

Run these before changing Git/GitHub state:

```bash
git rev-parse HEAD
git status --short --branch --untracked-files=all
git branch -a -vv
git remote -v
git bundle create .runtime-cache/closeout/backups/apple-notes-snapshot-<timestamp>.bundle --all
```

Record GitHub truth separately:

- branch protection / required checks
- Pages settings
- latest release target
- CodeQL / Dependabot / secret alert state
- current workflow run state

## 2. Promotion Gate: Stay In Place Or Hard Cut

Stay on the in-place closeout path only when **all** of these are true:

- current tree is preservable and reviewable
- history scans show no real leaked secrets
- history scans show no real machine-private paths outside tests/scanners
- public GitHub surfaces do not expose stale polluted content that the current
  repo can no longer control safely

Promote to hard cut immediately when any promotion condition from
[`ADR 0001`](../adr/0001-closeout-canonical-and-hard-cut-threshold.md) fires.

## 3. Repo-Owned Verification Ladder

Default local maintainer lane:

```bash
./notesctl rebuild-dev-env
./.runtime-cache/dev/venv/bin/python -m pre_commit run --all-files
PYTHON_BIN=./.runtime-cache/dev/venv/bin/python scripts/checks/ci_gate.sh
```

Optional local parity lane:

```bash
scripts/checks/actionlint_gate.sh
scripts/checks/zizmor_gate.sh
TRIVY_BIN=/path/to/trivy scripts/checks/trivy_fs_gate.sh
```

Reuse the five-layer CI contract in [README.md](../../README.md#ci-contract) as
the public SSOT. The closeout-only deltas are:

- `Dependency Review` must still pass on the pull request because it needs the
  PR base/head diff.
- `GitHub Alert Gate`, CodeQL, Secret Scan, Actionlint, Zizmor, and Trivy stay
  hosted-first. Local reruns remain optional maintainer repro steps, not part
  of the default pre-push contract.

## 4. GitHub Control Plane Checklist

Before final closeout, confirm:

- `Dependabot` / vulnerability alerts are enabled
- private vulnerability reporting is enabled
- `secret_scanning_non_provider_patterns` and `secret_scanning_validity_checks`
  are either enabled or explicitly recorded as platform capability residuals
- required checks match the current governance set
- latest release points at the current canonical closeout commit
- Pages homepage and README links still point at the current canonical entry

## 5. Release And Required-Check Convergence

Do not retarget old releases. Publish a new release from the final closeout
commit instead.

For the active closeout wave:

- the latest public tag stays historical once a newer closeout commit exists
- the next release should be cut from the final closeout commit instead of
  retargeting an older tag

Before release:

1. make the pull request green
2. merge the pull request
3. confirm the new `main` SHA is green on GitHub
4. publish the new release from that SHA

## 6. Hard-Cut Path

If the promotion gate fires:

1. preserve the current tree and bundle
2. rebuild a clean linear history in <= 10 commits
3. create the new canonical repository
4. restore Pages / required checks / topics / templates / releases as needed
5. verify fresh clone, CI, Pages, and release truth
6. retire the old public entry only after the new one is verified

## 7. Final Verdict Rules

Use only one of these verdicts:

- `FULLY_CLEAN_AND_CLOSED`
- `REPO_SIDE_CLEAN_BUT_PLATFORM_RESIDUAL_REMAINS`
- `BLOCKED_BY_TRUE_EXTERNAL_ONLY`
- `NOT_CLEAN_REQUIRES_FURTHER_REPAIR`

Do not collapse repo-side truth, GitHub control-plane truth, and platform
residuals into one sentence.
