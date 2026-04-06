## Summary

- what changed
- why it changed

## Verification

- [ ] `./notesctl doctor --json | ./.runtime-cache/dev/venv/bin/python -m json.tool`
- [ ] `./.runtime-cache/dev/venv/bin/python -m pre_commit run --all-files`
- [ ] `PYTHON_BIN=./.runtime-cache/dev/venv/bin/python scripts/checks/ci_gate.sh`
- [ ] `scripts/checks/actionlint_gate.sh`
- [ ] `scripts/checks/zizmor_gate.sh`
- [ ] `TRIVY_BIN=/path/to/trivy scripts/checks/trivy_fs_gate.sh`
- [ ] other relevant command(s) documented below

## Risk And Rollback

- risk level:
- rollback path:

## Governance Impact

- [ ] no public contract change
- [ ] updates root documentation
- [ ] touches launchd or path behavior
- [ ] touches vendor refresh or provenance
- [ ] touches Web UI auth or local control-plane behavior
- [ ] requires GitHub-side settings follow-up

## macOS / Local Assumptions

- Apple Notes / AppleScript assumptions:
- launchd assumptions:
- path or permission assumptions:

## Notes For Reviewers

- current tracked tree impact:
- Git history impact:
- GitHub control-plane follow-up:
