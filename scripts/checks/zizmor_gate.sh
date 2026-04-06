#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEFAULT_ZIZMOR_BIN="${REPO_ROOT}/.runtime-cache/dev/venv/bin/zizmor"
if [[ -z "${ZIZMOR_BIN:-}" && -x "${DEFAULT_ZIZMOR_BIN}" ]]; then
  ZIZMOR_BIN="${DEFAULT_ZIZMOR_BIN}"
else
  ZIZMOR_BIN="${ZIZMOR_BIN:-zizmor}"
fi
ZIZMOR_FORMAT="${ZIZMOR_FORMAT:-plain}"

cd "${REPO_ROOT}"

if ! command -v "${ZIZMOR_BIN}" >/dev/null 2>&1; then
  echo "zizmor gate failed: zizmor not found." >&2
  echo "Run ./notesctl rebuild-dev-env or set ZIZMOR_BIN=/absolute/path/to/zizmor." >&2
  exit 2
fi

args=(
  --persona auditor
  --no-online-audits
  --strict-collection
  --format "${ZIZMOR_FORMAT}"
  .github/workflows
)

if [[ -f ".github/dependabot.yml" ]]; then
  args+=(.github/dependabot.yml)
fi

"${ZIZMOR_BIN}" "${args[@]}"
