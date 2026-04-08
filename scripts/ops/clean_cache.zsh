#!/bin/zsh
set -euo pipefail

# ------------------------------
# Paths
# ------------------------------
SCRIPT_DIR="${0:A:h}"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LIB_COMMON="${REPO_ROOT}/scripts/lib/common.zsh"
LIB_CONFIG="${REPO_ROOT}/scripts/lib/config.zsh"

if [[ ! -f "$LIB_COMMON" ]]; then
  echo "missing lib/common: $LIB_COMMON" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$LIB_COMMON"

if [[ ! -f "$LIB_CONFIG" ]]; then
  echo "missing lib/config: $LIB_CONFIG" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$LIB_CONFIG"

validate_abs_path "REPO_ROOT" "$REPO_ROOT"
load_env_with_defaults

# ------------------------------
# Targets
# ------------------------------
TARGETS=(
  "${NOTES_SNAPSHOT_RUNTIME_ROOT}/dev/venv"
  "${NOTES_SNAPSHOT_CACHE_DIR}"
  "${NOTES_SNAPSHOT_TEMP_DIR}"
  "${NOTES_SNAPSHOT_RUNTIME_ROOT}/logs"
  "${NOTES_SNAPSHOT_PYTEST_CACHE_DIR}"
  "${NOTES_SNAPSHOT_COVERAGE_FILE:h}"
  "${NOTES_SNAPSHOT_PYTHONPYCACHEPREFIX}"
  "${NOTES_SNAPSHOT_RUNTIME_ROOT}/browser-proof"
  "${NOTES_SNAPSHOT_RUNTIME_ROOT}/phase1"
  "${NOTES_SNAPSHOT_RUNTIME_ROOT}/phase1-history-rebuild"
  "${NOTES_SNAPSHOT_RUNTIME_ROOT}/mcp-registry-lane/out"
  "${REPO_ROOT}/.pytest_cache"
  "${REPO_ROOT}/.coverage"
  "${REPO_ROOT}/.venv"
  "${REPO_ROOT}/tests/__pycache__"
  "${REPO_ROOT}/tests/unit/__pycache__"
  "${REPO_ROOT}/tests/e2e/__pycache__"
  "${REPO_ROOT}/scripts/ops/__pycache__"
  "${REPO_ROOT}/vendor/notes-exporter/__pycache__"
  "${REPO_ROOT}/vendor/notes-exporter/.pytest_cache"
)

MODE="apply"
removed=0
missing=0

usage() {
  cat <<USAGE
Usage:
  ./notesctl clean-cache --dry-run
  ./notesctl clean-cache [--apply]

Maintainer-only cleanup lane.
This command only removes repo-local rebuildables and disposable-generated files.
It never deletes exported snapshots under:
  ${NOTES_SNAPSHOT_ROOT_DIR}

Modes:
  --dry-run   preview local rebuildable cleanup targets without deleting them
  --apply     delete the same targets (default)
USAGE
}

class_for_target() {
  local target="$1"
  case "$target" in
    */.runtime-cache/dev/venv|*/.venv)
      printf '%s\n' "rebuildable-env"
      ;;
    */.runtime-cache/cache/apple-notes-snapshot)
      printf '%s\n' "runtime-cache"
      ;;
    */.runtime-cache/temp)
      printf '%s\n' "scratch"
      ;;
    */.runtime-cache/logs)
      printf '%s\n' "logs"
      ;;
    */.runtime-cache/pytest|*/.pytest_cache)
      printf '%s\n' "pytest-cache"
      ;;
    */.runtime-cache/coverage|*/.coverage)
      printf '%s\n' "coverage-data"
      ;;
    */.runtime-cache/pycache|*/__pycache__)
      printf '%s\n' "python-bytecode"
      ;;
    */.runtime-cache/browser-proof)
      printf '%s\n' "proof-captures"
      ;;
    */.runtime-cache/phase1|*/.runtime-cache/phase1-history-rebuild)
      printf '%s\n' "historical-rollback"
      ;;
    */.runtime-cache/mcp-registry-lane/out)
      printf '%s\n' "registry-stage"
      ;;
    *)
      printf '%s\n' "disposable-generated"
      ;;
  esac
}

rebuild_hint_for_target() {
  local target="$1"
  case "$target" in
    */.runtime-cache/dev/venv)
      printf '%s\n' "./notesctl rebuild-dev-env"
      ;;
    */.venv)
      printf '%s\n' "python -m venv .venv && source .venv/bin/activate"
      ;;
    */.runtime-cache/pytest|*/.runtime-cache/coverage|*/.runtime-cache/pycache|*/.runtime-cache/logs|*/.pytest_cache|*/.coverage|*/__pycache__)
      printf '%s\n' "rerun the documented repo workflow"
      ;;
    */.runtime-cache/browser-proof)
      printf '%s\n' "rerun the browser proof capture workflow if you still need screenshots"
      ;;
    */.runtime-cache/phase1|*/.runtime-cache/phase1-history-rebuild)
      printf '%s\n' "historical hard-cut rollback artifacts; keep only if you still need manual rollback evidence"
      ;;
    */.runtime-cache/mcp-registry-lane/out)
      printf '%s\n' "rerun scripts/release/build_mcp_registry_lane.zsh"
      ;;
    *)
      printf '%s\n' "rerun the documented repo workflow"
      ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      MODE="dry-run"
      ;;
    --apply)
      MODE="apply"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

echo "[clean-cache] maintainer-only lane; exported snapshots under ${NOTES_SNAPSHOT_ROOT_DIR} stay untouched"

for target in "${TARGETS[@]}"; do
  target_class="$(class_for_target "$target")"
  rebuild_hint="$(rebuild_hint_for_target "$target")"
  if [[ -e "$target" ]]; then
    rel_target="${target#$REPO_ROOT/}"
    if [[ "$MODE" == "dry-run" ]]; then
      echo "[clean-cache] would remove class=${target_class} path=${rel_target} rebuild='${rebuild_hint}'"
    else
      rm -rf -- "$target"
      echo "[clean-cache] removed class=${target_class} path=${rel_target} rebuild='${rebuild_hint}'"
      removed=$(( removed + 1 ))
    fi
  else
    rel_target="${target#$REPO_ROOT/}"
    echo "[clean-cache] missing class=${target_class} path=${rel_target}"
    missing=$(( missing + 1 ))
  fi
done

if [[ "$MODE" == "apply" && -d "${REPO_ROOT}/vendor/notes-exporter" ]]; then
  find "${REPO_ROOT}/vendor/notes-exporter" \
    \( -type d \( -name '__pycache__' -o -name '.pytest_cache' \) -prune -exec rm -rf {} + \) 2>/dev/null || true
  find "${REPO_ROOT}/vendor/notes-exporter" \
    \( -type f \( -name '*.pyc' -o -name '*.pyo' -o -path '*/tests/test_results.txt' \) -exec rm -f {} + \) 2>/dev/null || true
fi

echo "clean-cache done (mode=${MODE}, removed=${removed}, missing=${missing})"
echo "next: ./notesctl rebuild-dev-env"
echo "next: ./notesctl status --full"
echo "next: ./notesctl verify"
echo "next: ./notesctl doctor"
