# Repository Settings Checklist

This file is the manual control-plane checklist for settings that the tracked
tree cannot prove on its own.

Review these items whenever the public surface, release flow, or security
process changes:

## GitHub Control Plane

- Branch protection / rulesets for `main`
- Required checks align with the current closeout set:
  - `CodeQL (python)`
  - `CodeQL (javascript-typescript)`
  - `Canonical Quick Gate`
  - `Secret Scan`
  - `GitHub Alert Gate`
  - `Actionlint`
  - `Zizmor`
  - `Dependency Review`
  - `Trivy`
- Private vulnerability reporting is enabled
- Dependabot / vulnerability alerts are enabled
- Secret scanning is enabled
- Repository About description matches the README punchline
- Homepage URL points at the current public docs landing page
- Topics still match the current positioning
- Social preview still matches the current public-facing asset

## Recording

When a release or governance change touches one of these items, note the review
date and the maintainer who checked it in the PR or release notes.
