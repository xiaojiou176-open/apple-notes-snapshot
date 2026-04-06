#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TRIVY_BIN="${TRIVY_BIN:-trivy}"

cd "${REPO_ROOT}"

if ! command -v "${TRIVY_BIN}" >/dev/null 2>&1; then
  echo "trivy gate failed: trivy not found." >&2
  echo "Install Trivy or set TRIVY_BIN=/absolute/path/to/trivy." >&2
  exit 2
fi

"${TRIVY_BIN}" fs \
  --scanners vuln,secret \
  --severity HIGH,CRITICAL \
  --ignore-unfixed \
  --no-progress \
  --exit-code 1 \
  --skip-dirs .runtime-cache \
  --skip-dirs .agents \
  --skip-dirs .serena \
  --skip-dirs .claude-plugin \
  --skip-dirs .codex-plugin \
  --skip-dirs vendor/notes-exporter/.git \
  .
