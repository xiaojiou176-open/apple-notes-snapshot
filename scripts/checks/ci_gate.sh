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

# Pre-push hooks can export repo-specific Git variables that pollute temp-repo
# governance tests. Clear them before any Python or nested git subprocess runs.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY \
  GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR

"${PYTHON_BIN}" scripts/checks/docs_link_root_hygiene.py
"${PYTHON_BIN}" scripts/checks/legacy_path_scan.py
"${PYTHON_BIN}" scripts/checks/public_surface_sensitive_scan.py
"${PYTHON_BIN}" scripts/checks/github_alert_gate.py
bash "${SCRIPT_DIR}/vendor_tree_hygiene.sh"
bash "${SCRIPT_DIR}/run_unit_tests.sh"
bash "${SCRIPT_DIR}/run_wrapper_smoke.sh"
