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

./notesctl --help >/dev/null
./notesctl help run >/dev/null
./notesctl run --help >/dev/null
./notesctl help install >/dev/null
./notesctl install --help >/dev/null
./notesctl help ai-diagnose >/dev/null
./notesctl help mcp >/dev/null
./notesctl help web >/dev/null
./notesctl help audit >/dev/null
./notesctl help clean-cache >/dev/null
./notesctl clean-cache --help >/dev/null
./notesctl help runtime-audit >/dev/null
./notesctl runtime-audit --json | "${PYTHON_BIN}" -m json.tool >/dev/null
./notesctl help clean-runtime >/dev/null
./notesctl clean-runtime --help >/dev/null
./notesctl help browser-bootstrap >/dev/null
./notesctl browser-bootstrap --help >/dev/null
./notesctl help browser-open >/dev/null
./notesctl browser-open --help >/dev/null
./notesctl help browser-contract >/dev/null
./notesctl browser-contract --help >/dev/null
./notesctl status --json | "${PYTHON_BIN}" -m json.tool >/dev/null
./notesctl doctor --json | "${PYTHON_BIN}" -m json.tool >/dev/null
./notesctl ai-diagnose --json | "${PYTHON_BIN}" -m json.tool >/dev/null
