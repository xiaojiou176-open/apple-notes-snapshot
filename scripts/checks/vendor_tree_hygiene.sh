#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
VENDOR_ROOT="${REPO_ROOT}/vendor/notes-exporter"

if [[ ! -d "${VENDOR_ROOT}" ]]; then
  echo "vendor hygiene skipped (vendor/notes-exporter missing)"
  exit 0
fi

mapfile -t residue < <(
  find "${VENDOR_ROOT}" \
    \( -path '*/.pytest_cache*' -o -path '*/__pycache__*' -o -name '*.pyc' -o -name '*.pyo' -o -path '*/tests/test_results.txt' \) \
    | sort
)

if [[ "${#residue[@]}" -gt 0 ]]; then
  echo "vendor tree hygiene check failed:"
  printf ' - %s\n' "${residue[@]}"
  exit 1
fi

echo "vendor tree hygiene check passed"
