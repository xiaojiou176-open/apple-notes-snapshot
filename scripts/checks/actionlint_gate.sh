#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ACTIONLINT_BIN="${ACTIONLINT_BIN:-actionlint}"

cd "${REPO_ROOT}"

if ! command -v "${ACTIONLINT_BIN}" >/dev/null 2>&1; then
  echo "actionlint gate failed: actionlint not found in PATH." >&2
  echo "Install actionlint or set ACTIONLINT_BIN=/absolute/path/to/actionlint." >&2
  exit 2
fi

"${ACTIONLINT_BIN}" .github/workflows/*.yml
