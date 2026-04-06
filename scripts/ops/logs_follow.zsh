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

STDOUT_LOG="${NOTES_SNAPSHOT_LOG_DIR}/stdout.log"
STDERR_LOG="${NOTES_SNAPSHOT_LOG_DIR}/stderr.log"
LAUNCHD_OUT="${NOTES_SNAPSHOT_LOG_DIR}/launchd.out.log"
LAUNCHD_ERR="${NOTES_SNAPSHOT_LOG_DIR}/launchd.err.log"

# ------------------------------
# Args
# ------------------------------
TAIL_LINES="$NOTES_SNAPSHOT_TAIL_LINES"
SINCE_MINUTES=""
USE_STDOUT=0
USE_STDERR=0
USE_LAUNCHD=0
USE_ALL=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tail)
      TAIL_LINES="$2"
      shift 2
      ;;
    --since)
      SINCE_MINUTES="$2"
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

if [[ -n "$SINCE_MINUTES" ]]; then
  if [[ ! "$SINCE_MINUTES" =~ ^[0-9]+$ ]] || [[ "$SINCE_MINUTES" -le 0 ]]; then
    echo "invalid --since: $SINCE_MINUTES" >&2
    exit 1
  fi
fi

if [[ -z "$SINCE_MINUTES" ]]; then
  if [[ ! "$TAIL_LINES" =~ ^[0-9]+$ ]] || [[ "$TAIL_LINES" -le 0 ]]; then
    echo "invalid --tail: $TAIL_LINES" >&2
    exit 1
  fi
fi

# ------------------------------
# Follow logs
# ------------------------------
if [[ ! -d "$NOTES_SNAPSHOT_LOG_DIR" ]]; then
  echo "log dir missing: $NOTES_SNAPSHOT_LOG_DIR" >&2
  exit 1
fi

touch "$STDOUT_LOG" "$STDERR_LOG" "$LAUNCHD_OUT" "$LAUNCHD_ERR"

FILES=()
if [[ "$USE_ALL" -eq 1 ]]; then
  FILES+=("$STDOUT_LOG" "$STDERR_LOG" "$LAUNCHD_OUT" "$LAUNCHD_ERR")
else
  if [[ "$USE_STDOUT" -eq 1 ]]; then
    FILES+=("$STDOUT_LOG")
  fi
  if [[ "$USE_STDERR" -eq 1 ]]; then
    FILES+=("$STDERR_LOG")
  fi
  if [[ "$USE_LAUNCHD" -eq 1 ]]; then
    FILES+=("$LAUNCHD_OUT" "$LAUNCHD_ERR")
  fi
fi

if [[ "${#FILES[@]}" -eq 0 ]]; then
  echo "no log files selected; use --all or --stdout/--stderr/--launchd" >&2
  exit 1
fi

if [[ -n "$SINCE_MINUTES" ]]; then
  CUTOFF="$(date -v -"${SINCE_MINUTES}"M '+%Y-%m-%d %H:%M:%S')"
  for file in "${FILES[@]}"; do
    if [[ -f "$file" ]]; then
      awk -v cutoff="$CUTOFF" '
        {
          line = $0
          if (match(line, /^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}/)) {
            ts = substr(line, 1, 19)
            if (ts >= cutoff) print line
          } else {
            print line
          }
        }
      ' "$file"
    fi
  done
  tail -n 0 -F "${FILES[@]}"
else
  tail -n "$TAIL_LINES" -F "${FILES[@]}"
fi
