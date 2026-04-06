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

if [[ ! -f "$LIB_COMMON" ]]; then
  echo "missing lib/common: $LIB_COMMON" >&2
  exit 1
fi

if [[ ! -f "$LIB_CONFIG" ]]; then
  echo "missing lib/config: $LIB_CONFIG" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$LIB_COMMON"

# shellcheck disable=SC1090
source "$LIB_CONFIG"

# ------------------------------
# Load config
# ------------------------------
load_env_with_defaults

# ------------------------------
# Args
# ------------------------------
MAX_BYTES="$NOTES_SNAPSHOT_LOG_MAX_BYTES"
BACKUPS="$NOTES_SNAPSHOT_LOG_BACKUPS"
ROTATE_MODE="$NOTES_SNAPSHOT_LOG_ROTATE_MODE"
USE_STDOUT=0
USE_STDERR=0
USE_LAUNCHD=0
USE_METRICS=0
USE_STRUCTURED=0
USE_WEBUI=0
USE_ALL=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-bytes)
      MAX_BYTES="$2"
      shift 2
      ;;
    --backups)
      BACKUPS="$2"
      shift 2
      ;;
    --mode)
      ROTATE_MODE="$2"
      shift 2
      ;;
    --stdout)
      USE_STDOUT=1
      USE_ALL=0
      shift
      ;;
    --stderr)
      USE_STDERR=1
      USE_ALL=0
      shift
      ;;
    --launchd)
      USE_LAUNCHD=1
      USE_ALL=0
      shift
      ;;
    --metrics)
      USE_METRICS=1
      USE_ALL=0
      shift
      ;;
    --webui)
      USE_WEBUI=1
      USE_ALL=0
      shift
      ;;
    --structured)
      USE_STRUCTURED=1
      USE_ALL=0
      shift
      ;;
    --all)
      USE_ALL=1
      shift
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

validate_uint "NOTES_SNAPSHOT_LOG_MAX_BYTES" "$MAX_BYTES"
validate_uint "NOTES_SNAPSHOT_LOG_BACKUPS" "$BACKUPS"
if [[ "$MAX_BYTES" -le 0 ]]; then
  echo "NOTES_SNAPSHOT_LOG_MAX_BYTES must be > 0" >&2
  exit 1
fi
if [[ "$BACKUPS" -lt 1 ]]; then
  echo "NOTES_SNAPSHOT_LOG_BACKUPS must be >= 1" >&2
  exit 1
fi
if [[ "$ROTATE_MODE" != "copytruncate" && "$ROTATE_MODE" != "rename" ]]; then
  echo "invalid --mode: $ROTATE_MODE (use copytruncate|rename)" >&2
  exit 1
fi

FILES=()
if [[ "$USE_ALL" -eq 1 ]]; then
  FILES+=(
    "${NOTES_SNAPSHOT_LOG_DIR}/stdout.log"
    "${NOTES_SNAPSHOT_LOG_DIR}/stderr.log"
    "${NOTES_SNAPSHOT_LOG_DIR}/launchd.out.log"
    "${NOTES_SNAPSHOT_LOG_DIR}/launchd.err.log"
    "${NOTES_SNAPSHOT_LOG_DIR}/webui.out.log"
    "${NOTES_SNAPSHOT_LOG_DIR}/webui.err.log"
    "${NOTES_SNAPSHOT_LOG_DIR}/structured.jsonl"
    "${NOTES_SNAPSHOT_STATE_DIR}/metrics.jsonl"
    "${NOTES_SNAPSHOT_STATE_DIR}/phase_metrics.log"
  )
else
  if [[ "$USE_STDOUT" -eq 1 ]]; then
    FILES+=("${NOTES_SNAPSHOT_LOG_DIR}/stdout.log")
  fi
  if [[ "$USE_STDERR" -eq 1 ]]; then
    FILES+=("${NOTES_SNAPSHOT_LOG_DIR}/stderr.log")
  fi
  if [[ "$USE_LAUNCHD" -eq 1 ]]; then
    FILES+=("${NOTES_SNAPSHOT_LOG_DIR}/launchd.out.log" "${NOTES_SNAPSHOT_LOG_DIR}/launchd.err.log")
  fi
  if [[ "$USE_WEBUI" -eq 1 ]]; then
    FILES+=("${NOTES_SNAPSHOT_LOG_DIR}/webui.out.log" "${NOTES_SNAPSHOT_LOG_DIR}/webui.err.log")
  fi
  if [[ "$USE_METRICS" -eq 1 ]]; then
    FILES+=("${NOTES_SNAPSHOT_STATE_DIR}/metrics.jsonl" "${NOTES_SNAPSHOT_STATE_DIR}/phase_metrics.log")
  fi
  if [[ "$USE_STRUCTURED" -eq 1 ]]; then
    FILES+=("${NOTES_SNAPSHOT_LOG_DIR}/structured.jsonl")
  fi
fi

if [[ "${#FILES[@]}" -eq 0 ]]; then
  echo "no log files selected; use --all or --stdout/--stderr/--launchd/--webui/--metrics/--structured" >&2
  exit 1
fi

rotate_files_summary "$MAX_BYTES" "$BACKUPS" "$ROTATE_MODE" "${FILES[@]}"
