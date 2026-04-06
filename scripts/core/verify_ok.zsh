#!/bin/zsh
set -euo pipefail

# ------------------------------
# Paths
# ------------------------------
SCRIPT_DIR="${0:A:h}"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${REPO_ROOT}/config/notes_snapshot.env"
LIB_COMMON="${REPO_ROOT}/scripts/lib/common.zsh"
LIB_CONFIG="${REPO_ROOT}/scripts/lib/config.zsh"
LIB_STATE="${REPO_ROOT}/scripts/lib/state.zsh"

if [[ ! -f "$LIB_COMMON" ]]; then
  echo "missing lib/common: $LIB_COMMON" >&2
  exit 1
fi

if [[ ! -f "$LIB_CONFIG" ]]; then
  echo "missing lib/config: $LIB_CONFIG" >&2
  exit 1
fi

if [[ ! -f "$LIB_STATE" ]]; then
  echo "missing lib/state: $LIB_STATE" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$LIB_COMMON"

# shellcheck disable=SC1090
source "$LIB_CONFIG"

# shellcheck disable=SC1090
source "$LIB_STATE"

# ------------------------------
# Load config
# ------------------------------
load_env_with_defaults

state_set_paths "$NOTES_SNAPSHOT_STATE_DIR"

# ------------------------------
# Check
# ------------------------------
state_load_state_prefer_json "$STATE_FILE" "$LAST_RUN_FILE" "$LAST_SUCCESS_FILE" "$STATE_JSON_FILE"

if [[ -z "${last_success_epoch:-}" ]]; then
  if [[ ! -f "$STATE_JSON_FILE" && ! -f "$LAST_SUCCESS_FILE" ]]; then
    echo "FAIL: no last_success record; run ./notesctl run"
  else
    echo "FAIL: last_success_epoch missing"
  fi
  exit 2
fi

NOW_EPOCH="$(date +%s)"
AGE_SEC=$(( NOW_EPOCH - last_success_epoch ))

if [[ "$AGE_SEC" -gt "$NOTES_SNAPSHOT_STALE_THRESHOLD_SEC" ]]; then
  echo "WARN: last success is stale (${AGE_SEC}s > ${NOTES_SNAPSHOT_STALE_THRESHOLD_SEC}s)"
  exit 1
fi

EXPECTED_SEC=$(( NOTES_SNAPSHOT_INTERVAL_MINUTES * 60 ))
if [[ "$AGE_SEC" -gt "$EXPECTED_SEC" ]]; then
  echo "WARN: last success is older than interval (${AGE_SEC}s > ${EXPECTED_SEC}s)"
  exit 1
fi

echo "OK: last success is fresh (${AGE_SEC}s)"
