#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEFAULT_PYTHON_BIN="${REPO_ROOT}/.runtime-cache/dev/venv/bin/python"
if [[ -z "${PYTHON_BIN:-}" && -x "${DEFAULT_PYTHON_BIN}" ]]; then
  PYTHON_BIN="${DEFAULT_PYTHON_BIN}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

cd "${REPO_ROOT}"

# Keep repo-local disposable Python/test artifacts under .runtime-cache.
export PYTHONPYCACHEPREFIX="${REPO_ROOT}/.runtime-cache/pycache"
export COVERAGE_FILE="${REPO_ROOT}/.runtime-cache/coverage/.coverage"
mkdir -p "${REPO_ROOT}/.runtime-cache/coverage"

# Coverage data is repo-local and rebuildable. Clear stale files first so a
# previous run from a different interpreter/schema does not taint the current gate.
rm -f "${COVERAGE_FILE}" "${COVERAGE_FILE}".*

"${PYTHON_BIN}" -m pytest \
  --cov=scripts/ops \
  --cov-report=term-missing \
  --cov-fail-under=90 \
  tests/unit \
  "$@"
