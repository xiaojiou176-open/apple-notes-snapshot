#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LIB_COMMON="${REPO_ROOT}/scripts/lib/common.zsh"

if [[ ! -f "$LIB_COMMON" ]]; then
  echo "missing lib/common: $LIB_COMMON" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$LIB_COMMON"

validate_abs_path "REPO_ROOT" "$REPO_ROOT"

VENV_DIR="${REPO_ROOT}/.runtime-cache/dev/venv"
PYTHON_BIN="${NOTES_SNAPSHOT_DEV_PYTHON_BIN:-}"
PRINT_ONLY=0
MIN_DEV_PYTHON_MAJOR=3
MIN_DEV_PYTHON_MINOR=11

resolve_python_candidate() {
  local candidate="$1"
  local resolved=""

  if [[ -z "$candidate" ]]; then
    return 1
  fi

  if [[ "$candidate" == */* ]]; then
    if [[ -x "$candidate" ]]; then
      printf '%s' "$candidate"
      return 0
    fi
    return 1
  fi

  resolved="$(command -v "$candidate" 2>/dev/null || true)"
  if [[ -n "$resolved" ]]; then
    printf '%s' "$resolved"
    return 0
  fi

  return 1
}

python_meets_min_version() {
  local candidate="$1"
  "$candidate" - "$MIN_DEV_PYTHON_MAJOR" "$MIN_DEV_PYTHON_MINOR" <<'PY'
import sys

minimum = (int(sys.argv[1]), int(sys.argv[2]))
sys.exit(0 if sys.version_info >= minimum else 1)
PY
}

find_dev_python() {
  local requested="${1:-}"
  local resolved=""
  local -a candidates=()

  if [[ -n "$requested" ]]; then
    candidates+=("$requested")
  else
    # Prefer versioned interpreter paths before generic python3/python aliases.
    # On Homebrew-managed machines the unversioned alias can jump to a newer
    # minor release before the repo-owned venv/tooling path has been proven there.
    if [[ -n "${HOMEBREW_PREFIX:-}" ]]; then
      candidates+=(
        "${HOMEBREW_PREFIX}/bin/python3.13"
        "${HOMEBREW_PREFIX}/bin/python3.12"
        "${HOMEBREW_PREFIX}/bin/python3.11"
        "${HOMEBREW_PREFIX}/bin/python3.14"
        "${HOMEBREW_PREFIX}/bin/python3"
      )
    fi
    candidates+=(
      /opt/homebrew/bin/python3.13
      /opt/homebrew/bin/python3.12
      /opt/homebrew/bin/python3.11
      /opt/homebrew/bin/python3.14
      /opt/homebrew/bin/python3
      /usr/local/bin/python3.13
      /usr/local/bin/python3.12
      /usr/local/bin/python3.11
      /usr/local/bin/python3.14
      /usr/local/bin/python3
      /Library/Frameworks/Python.framework/Versions/Current/bin/python3
      python3
      python
    )
  fi

  local candidate=""
  for candidate in "${candidates[@]}"; do
    resolved="$(resolve_python_candidate "$candidate")" || continue
    if python_meets_min_version "$resolved"; then
      printf '%s' "$resolved"
      return 0
    fi
  done

  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv-dir)
      VENV_DIR="$2"
      shift 2
      ;;
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --print-only)
      PRINT_ONLY=1
      shift
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

validate_abs_path "VENV_DIR" "$VENV_DIR"

PYTHON_BIN="$(find_dev_python "$PYTHON_BIN")" || die "python ${MIN_DEV_PYTHON_MAJOR}.${MIN_DEV_PYTHON_MINOR}+ not found; install a newer local Python or pass --python /path/to/python3"

REQ_VENDOR="${REPO_ROOT}/vendor/notes-exporter/requirements.txt"
REQ_DEV="${REPO_ROOT}/requirements-dev.txt"
REQ_VENDOR_RUNTIME="${VENV_DIR:h}/vendor-runtime.requirements.txt"

require_file "$REQ_VENDOR"
require_file "$REQ_DEV"

if [[ "$VENV_DIR" == "/" || "$VENV_DIR" == "$HOME" || "$VENV_DIR" == "$REPO_ROOT" ]]; then
  die "refusing to recreate unsafe venv dir: $VENV_DIR"
fi

if [[ "$PRINT_ONLY" -eq 1 ]]; then
  cat <<EOF
repo_root=$REPO_ROOT
venv_dir=$VENV_DIR
python_bin=$(command -v "$PYTHON_BIN")
vendor_requirements=$REQ_VENDOR
vendor_runtime_requirements=$REQ_VENDOR_RUNTIME
dev_requirements=$REQ_DEV
EOF
  exit 0
fi

ensure_dir "${VENV_DIR:h}"
grep -v -E '^[[:space:]]*pytest([[:space:]]*(#.*)?)?$' "$REQ_VENDOR" > "$REQ_VENDOR_RUNTIME"
rm -rf -- "$VENV_DIR"
"$PYTHON_BIN" -m venv "$VENV_DIR"

PY_BIN="${VENV_DIR}/bin/python"
PYTEST_BIN="${VENV_DIR}/bin/pytest"

require_exec "$PY_BIN"

# Some newer Python builds can leave pip partially bootstrapped after `venv`
# creation. Normalize the repo-owned environment before installing deps.
"$PY_BIN" -m ensurepip --upgrade

"$PY_BIN" -m pip install -r "$REQ_VENDOR_RUNTIME"
"$PY_BIN" -m pip install -r "$REQ_DEV"

cat <<EOF
rebuild-dev-env done
repo_root=$REPO_ROOT
venv_dir=$VENV_DIR
python_bin=$PY_BIN
pytest_bin=$PYTEST_BIN
vendor_runtime_requirements=$REQ_VENDOR_RUNTIME
next_unit=$PYTEST_BIN tests/unit
next_e2e=$PYTEST_BIN tests/e2e --no-cov
EOF
