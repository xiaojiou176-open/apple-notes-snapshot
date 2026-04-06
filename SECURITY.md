# Security Policy

## Supported Scope

This repository is maintained as a local-first macOS utility for exporting and
snapshotting Apple Notes. Security reports are welcome for:

- command execution or privilege-boundary bugs in `notesctl`
- token/auth issues in the optional local Web UI
- unsafe file writes, path traversal, or destructive automation behavior
- accidental credential, token, or personal-data exposure in logs or docs

## Reporting A Vulnerability

Please do not file high-impact vulnerabilities in a public issue first.

Report privately with:

- affected version or commit
- clear reproduction steps
- impact summary
- whether personal notes or secrets may have been exposed

Do not include exported note content, live tokens, or full diagnostic logs in a
public report.

## Private Disclosure Status

This repository uses **GitHub private vulnerability reporting** as the intended
private disclosure path.

Preferred path:

1. Use GitHub's `Report a vulnerability` flow when the repository UI shows it.
2. Share impact, affected version/commit, and reproduction steps there instead
   of in a public issue.

Fallback path:

1. If GitHub's private reporting entry point is unavailable in your current UI,
   open a minimal public issue without exploit details, note samples, or
   secrets. Prefer the `Security contact request` issue template if GitHub is
   showing it.
2. State that you need a private disclosure path before sharing reproducer
   steps or sensitive artifacts.
3. Wait for maintainer follow-up before sending full details anywhere else.

GitHub-only settings such as Secret Scanning alert visibility, private
vulnerability reporting, and required checks remain remote repo settings. The
source tree can document the intended flow, but the live enablement state still
belongs to the GitHub control plane.

Use `.github/REPOSITORY_SETTINGS_CHECKLIST.md` as the manual review checklist
when the public security or release surface changes.

Keep these statements separate in security discussions:

- what the current tracked tree proves
- what Git history proves
- what GitHub settings prove

## Repo-Managed Safety Nets

This repository can still prove a smaller, local safety surface:

- committed `pre-commit` / `pre-push` hooks for `gitleaks` and repo-surface
  hygiene
- committed GitHub workflows for CodeQL, secret/hygiene gates, actionlint,
  zizmor, Trivy, and dependency review
- a minimal public fallback path that does not ask reporters to post notes,
  secrets, or exploit details in the clear

## Response Expectations

- Initial triage target: within 7 days
- Follow-up: fix, mitigation guidance, or explicit risk assessment

## Safety Notes

- This project is intended to run against your own Apple Notes account and your
  own export destination.
- Review `config/notes_snapshot.env` carefully before enabling remote Web UI
  access or custom launchd watch paths.
