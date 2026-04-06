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
# Args
# ------------------------------
MODE="full"
TAIL_LINES=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --brief)
      MODE="brief"
      shift
      ;;
    --full)
      MODE="full"
      shift
      ;;
    --verbose)
      MODE="verbose"
      shift
      ;;
    --json)
      MODE="json"
      shift
      ;;
    --tail)
      TAIL_LINES="$2"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

# ------------------------------
# Load config
# ------------------------------
load_env_with_defaults
STATE_SCHEMA_VERSION_EXPECTED="1"
LAUNCHD_LABEL="${NOTES_SNAPSHOT_LAUNCHD_LABEL:-local.apple-notes-snapshot}"

if [[ -z "$TAIL_LINES" ]]; then
  TAIL_LINES="$NOTES_SNAPSHOT_TAIL_LINES"
fi
if [[ ! "$TAIL_LINES" =~ ^[0-9]+$ ]] || [[ "$TAIL_LINES" -le 0 ]]; then
  echo "invalid --tail: $TAIL_LINES" >&2
  exit 1
fi

state_set_paths "$NOTES_SNAPSHOT_STATE_DIR"
VENDOR_INFO="${REPO_ROOT}/vendor/notes-exporter/VENDOR_INFO"

# ------------------------------
# Helpers
# ------------------------------
print_kv_file() {
  local label="$1"
  local file="$2"
  if [[ -f "$file" ]]; then
    echo "$label"
    cat "$file"
    echo ""
  else
    echo "$label"
    echo "  (missing)"
    echo ""
  fi
}

find_python_bin() {
  local py=""
  py="$(state_find_python)" || return 1
  printf '%s' "$py"
}

print_phases_from_json() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    return 0
  fi
  local py
  py="$(find_python_bin)" || return 0
  "$py" - "$file" <<'PY'
import json
import sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    sys.exit(0)

phases = data.get("phases")
if not phases:
    sys.exit(0)

print("Phases")
for name in sorted(phases.keys()):
    try:
        duration = int(phases[name])
    except Exception:
        duration = phases[name]
    print(f"  {name}: {duration}s")
print("")
PY
}

print_pipeline_exit_reason() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    return 0
  fi
  local py
  py="$(find_python_bin)" || return 0
  "$py" - "$file" <<'PY'
import json
import sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    sys.exit(0)

reason = data.get("pipeline_exit_reason")
if not reason:
    sys.exit(0)

print("Pipeline")
print(f"  exit_reason: {reason}")
print("")
PY
}

# ------------------------------
# Schema info
# ------------------------------
print_schema_info() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    return 0
  fi
  local py
  py="$(find_python_bin)" || return 0
  "$py" - "$file" "$STATE_SCHEMA_VERSION_EXPECTED" "${CHECKSUM_STATUS:-unknown}" "${CHECKSUM_WARNING:-}" <<'PY'
import json
import sys

path = sys.argv[1]
expected = sys.argv[2]
checksum_status = sys.argv[3] if len(sys.argv) > 3 else "unknown"
checksum_warning = sys.argv[4] if len(sys.argv) > 4 else ""
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    sys.exit(0)

version = data.get("schema_version")
print("Schema")
if version is None:
    print("  version: (missing)")
    print("  warning: legacy state.json without schema_version")
else:
    print(f"  version: {version}")
    if str(version) != str(expected):
        print(f"  warning: schema_version mismatch (expected {expected})")
if checksum_status != "unknown":
    print(f"  checksum: {checksum_status}")
    if checksum_warning:
        print(f"  warning: {checksum_warning}")
print("")
PY
}

# ------------------------------
# Metrics JSONL
# ------------------------------
print_metrics_jsonl_summary() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    return 0
  fi
  local py
  py="$(find_python_bin)" || return 0
  "$py" - "$file" <<'PY'
import json
import sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
except Exception:
    sys.exit(0)

if not lines:
    sys.exit(0)

last = lines[-1]
try:
    data = json.loads(last)
except Exception:
    sys.exit(0)

print("Metrics")
event = data.get("event", "unknown")
status = data.get("status", "unknown")
duration = data.get("duration_sec", "unknown")
exit_code = data.get("exit_code", "unknown")
pipeline_exit_reason = data.get("pipeline_exit_reason", "")
print(f"  last_event: {event}")
print(f"  status: {status}")
print(f"  exit_code: {exit_code}")
print(f"  duration_sec: {duration}")
if pipeline_exit_reason:
    print(f"  pipeline_exit_reason: {pipeline_exit_reason}")
print("")
PY
}

# ------------------------------
# Health + JSON helpers
# ------------------------------
calc_health_score() {
  local score=100
  local -a reasons=()
  local status_value="${STATE_STATUS:-unknown}"
  local exit_value="${exit_code:-}"
  local has_extra_health_issues="0"

  if [[ "$LAUNCHD_STATE" == "not_loaded" ]]; then
    score=$(( score - 20 ))
    reasons+=("launchd_not_loaded")
  fi
  if [[ "$status_value" == "failed" || "$status_value" == "aborted" ]]; then
    score=$(( score - 40 ))
    reasons+=("last_run_failed")
  elif [[ "$status_value" == "running" ]]; then
    score=$(( score - 10 ))
    reasons+=("running")
  fi
  if [[ "$exit_value" =~ ^[0-9]+$ ]] && [[ "$exit_value" -ne 0 ]]; then
    score=$(( score - 20 ))
    reasons+=("exit_nonzero")
  fi
  if [[ "$exit_value" =~ ^[0-9]+$ ]]; then
    if [[ "$status_value" == "success" && "$exit_value" -ne 0 ]]; then
      reasons+=("status_exit_mismatch")
    elif [[ "$status_value" == "failed" && "$exit_value" -eq 0 ]]; then
      reasons+=("status_exit_mismatch")
    fi
  fi
  if [[ "$STALE" == "yes" ]]; then
    score=$(( score - 40 ))
    reasons+=("stale")
  elif [[ "$STALE" == "unknown" ]]; then
    score=$(( score - 20 ))
    reasons+=("unknown_last_success")
  fi
  if [[ "${CHECKSUM_STATUS:-}" == "mismatch" ]]; then
    score=$(( score - 10 ))
    reasons+=("checksum_mismatch")
    has_extra_health_issues="1"
  elif [[ "${CHECKSUM_STATUS:-}" == "missing" ]]; then
    score=$(( score - 10 ))
    reasons+=("checksum_missing")
    has_extra_health_issues="1"
  fi
  if [[ "${LOG_HEALTH_ERRORS_TOTAL:-0}" -gt 0 ]]; then
    if [[ "${LOG_HEALTH_ERRORS_TOTAL:-0}" -ge 5 ]]; then
      score=$(( score - 20 ))
    else
      score=$(( score - 10 ))
    fi
    reasons+=("log_health_errors")
    has_extra_health_issues="1"
  fi
  if [[ "$status_value" != "unknown" && "$status_value" != "running" ]]; then
    has_extra_health_issues="1"
  fi
  if [[ "$STALE" == "yes" ]]; then
    has_extra_health_issues="1"
  fi
  if [[ -n "${failure_reason:-}" ]]; then
    has_extra_health_issues="1"
  fi
  if [[ "$STALE" == "unknown" && "$status_value" == "unknown" && -z "$exit_value" && "$has_extra_health_issues" == "0" && "$score" -lt 70 ]]; then
    score=70
  fi

  if [[ "$score" -lt 0 ]]; then
    score=0
  fi

  local level="OK"
  if [[ "$score" -lt 40 ]]; then
    level="FAIL"
  elif [[ "$score" -lt 70 ]]; then
    level="DEGRADED"
  elif [[ "$score" -lt 90 ]]; then
    level="WARN"
  fi

  HEALTH_SCORE="$score"
  HEALTH_LEVEL="$level"
  HEALTH_REASONS="${(j:, :)reasons}"
  HEALTH_REASONS_CSV="${(j:,:)reasons}"
}

derive_state_layers() {
  CONFIG_LAYER_STATUS="configured"
  CONFIG_LAYER_SUMMARY="Config surface resolved for root, state, logs, and interval."

  LAUNCHD_LAYER_STATUS="${LAUNCHD_STATE:-unknown}"
  if [[ "$LAUNCHD_LAYER_STATUS" == "unknown" ]] && ! command -v launchctl >/dev/null 2>&1; then
    LAUNCHD_LAYER_STATUS="not_loaded"
  fi
  case "${LAUNCHD_LAYER_STATUS}" in
    loaded)
      LAUNCHD_LAYER_SUMMARY="launchctl reports ${LAUNCHD_LABEL} is loaded."
      ;;
    not_loaded)
      LAUNCHD_LAYER_SUMMARY="launchctl does not currently report ${LAUNCHD_LABEL} as loaded."
      ;;
    *)
      LAUNCHD_LAYER_SUMMARY="launchctl state could not be determined."
      ;;
  esac

  local status_value="${STATE_STATUS:-unknown}"
  if [[ -n "${last_success_epoch:-}" ]]; then
    if [[ "$STALE" == "yes" ]]; then
      LEDGER_LAYER_STATUS="stale"
      LEDGER_LAYER_SUMMARY="A successful snapshot exists, but it is older than the freshness threshold."
    else
      LEDGER_LAYER_STATUS="fresh"
      LEDGER_LAYER_SUMMARY="A successful snapshot is recorded in the local state ledger."
    fi
  elif [[ "$status_value" == "running" ]]; then
    LEDGER_LAYER_STATUS="running_without_success"
    LEDGER_LAYER_SUMMARY="A run is active, but the ledger has not recorded a successful snapshot yet."
  elif [[ "$status_value" == "failed" || "$status_value" == "aborted" ]]; then
    LEDGER_LAYER_STATUS="failed"
    LEDGER_LAYER_SUMMARY="The ledger recorded a failed run and still has no successful snapshot."
  else
    LEDGER_LAYER_STATUS="needs_first_run"
    LEDGER_LAYER_SUMMARY="No successful snapshot is recorded yet. Run one manual snapshot to initialize the ledger."
  fi
}

derive_health_summary() {
  local launchd_status="${LAUNCHD_LAYER_STATUS:-unknown}"
  local ledger_status="${LEDGER_LAYER_STATUS:-unknown}"
  local log_errors="${LOG_HEALTH_ERRORS_TOTAL:-0}"

  if [[ "$ledger_status" == "needs_first_run" ]]; then
    HEALTH_SUMMARY="Config and launchd look readable, but the ledger still needs the first successful snapshot baseline."
  elif [[ "$ledger_status" == "running_without_success" ]]; then
    HEALTH_SUMMARY="A snapshot run is active, but the ledger has not recorded a successful baseline yet."
  elif [[ "$ledger_status" == "stale" ]]; then
    HEALTH_SUMMARY="A successful snapshot exists, but it is older than the freshness target."
  elif [[ "$ledger_status" == "failed" ]]; then
    HEALTH_SUMMARY="The local ledger points to a failed run and still needs a successful recovery baseline."
  elif [[ "$launchd_status" == "not_loaded" ]]; then
    HEALTH_SUMMARY="The local scheduler is not loaded right now, so the backup loop is not running on its own."
  elif [[ "$log_errors" -gt 0 ]]; then
    HEALTH_SUMMARY="Recent log health signals show runtime errors even though the control-room state surface is present."
  else
    HEALTH_SUMMARY="The current local backup surface looks healthy enough to keep using the deterministic tooling as the source of truth."
  fi
}

print_state_layers_block() {
  echo "State Layers"
  echo "  config: ${CONFIG_LAYER_STATUS} - ${CONFIG_LAYER_SUMMARY}"
  echo "  launchd: ${LAUNCHD_LAYER_STATUS} - ${LAUNCHD_LAYER_SUMMARY}"
  echo "  ledger: ${LEDGER_LAYER_STATUS} - ${LEDGER_LAYER_SUMMARY}"
  echo ""
}

print_health_block() {
  local reasons="${HEALTH_REASONS:-}"
  if [[ -z "$reasons" ]]; then
    reasons="(none)"
  fi
  echo "Health"
  echo "  score: ${HEALTH_SCORE}"
  echo "  level: ${HEALTH_LEVEL}"
  echo "  summary: ${HEALTH_SUMMARY:-}"
  echo "  reasons: ${reasons}"
  echo ""
}

print_phases_bar_from_json() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    return 0
  fi
  local py
  py="$(find_python_bin)" || return 0
  "$py" - "$file" <<'PY' || return 0
import json
import sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    sys.exit(0)

phases = data.get("phases") or {}
items = []
total = 0
for name, value in phases.items():
    try:
        duration = int(value)
    except Exception:
        continue
    if duration < 0:
        continue
    items.append((name, duration))
    total += duration

if not items or total <= 0:
    sys.exit(0)

width = 30
print("Phases Chart")
for name, duration in sorted(items, key=lambda x: x[1], reverse=True):
    ratio = duration / total if total else 0
    bar_len = int(round(width * ratio))
    if bar_len <= 0 and duration > 0:
        bar_len = 1
    if bar_len > width:
        bar_len = width
    bar = "#" * bar_len + "-" * (width - bar_len)
    percent = int(round(ratio * 100))
    print(f"  {name}: [{bar}] {duration}s ({percent}%)")
print("")
PY
}

print_status_json() {
  local file="$1"
  local reasons_csv="${HEALTH_REASONS_CSV:-}"
  local status_value="${STATE_STATUS:-unknown}"
  local exit_value="${exit_code:-}"
  local last_run_value="${last_run_iso:-unknown}"
  local last_success_value="${last_success_iso:-unknown}"
  local trigger_value="${trigger_source:-unknown}"
  local run_id_value="${run_id:-}"

  export STATUS_JSON_STATUS="$status_value"
  export STATUS_JSON_EXIT_CODE="$exit_value"
  export STATUS_JSON_LAST_RUN_ISO="$last_run_value"
  export STATUS_JSON_LAST_SUCCESS_ISO="$last_success_value"
  export STATUS_JSON_TRIGGER_SOURCE="$trigger_value"
  export STATUS_JSON_RUN_ID="$run_id_value"
  export STATUS_JSON_CHECKSUM_STATUS="${CHECKSUM_STATUS:-unknown}"
  export STATUS_JSON_CHECKSUM_WARNING="${CHECKSUM_WARNING:-}"
  export STATUS_JSON_AGE_SEC="${AGE_SEC:-}"
  export STATUS_JSON_STALE="$STALE"
  export STATUS_JSON_INTERVAL_MINUTES="$NOTES_SNAPSHOT_INTERVAL_MINUTES"
  export STATUS_JSON_LAUNCHD="$LAUNCHD_STATE"
  export STATUS_JSON_HEALTH_SCORE="${HEALTH_SCORE:-0}"
  export STATUS_JSON_HEALTH_LEVEL="${HEALTH_LEVEL:-unknown}"
  export STATUS_JSON_HEALTH_REASONS="$reasons_csv"
  export STATUS_JSON_STATE_JSON_FILE="$file"
  export STATUS_JSON_METRICS_JSONL_FILE="$METRICS_JSONL_FILE"
  export STATUS_JSON_SCHEMA_VERSION_EXPECTED="$STATE_SCHEMA_VERSION_EXPECTED"
  export STATUS_JSON_SCHEMA_WARNING="${SCHEMA_WARNING:-}"
  export STATUS_JSON_LOG_HEALTH_TAIL_LINES="$TAIL_LINES"
  export STATUS_JSON_LOG_HEALTH_PATTERN="$NOTES_SNAPSHOT_LOG_HEALTH_PATTERN"
  export STATUS_JSON_LOG_HEALTH_ERRORS_STDOUT="${LOG_HEALTH_ERRORS_STDOUT:-0}"
  export STATUS_JSON_LOG_HEALTH_ERRORS_STDERR="${LOG_HEALTH_ERRORS_STDERR:-0}"
  export STATUS_JSON_LOG_HEALTH_ERRORS_LAUNCHD="${LOG_HEALTH_ERRORS_LAUNCHD:-0}"
  export STATUS_JSON_LOG_HEALTH_ERRORS_TOTAL="${LOG_HEALTH_ERRORS_TOTAL:-0}"
  export STATUS_JSON_ROOT_DIR="${NOTES_SNAPSHOT_ROOT_DIR}"
  export STATUS_JSON_LOG_DIR="${NOTES_SNAPSHOT_LOG_DIR}"
  export STATUS_JSON_STATE_DIR="${NOTES_SNAPSHOT_STATE_DIR}"
  export STATUS_JSON_LAUNCHD_LABEL="${LAUNCHD_LABEL}"
  export STATUS_JSON_HEALTH_SUMMARY="${HEALTH_SUMMARY:-}"
  export STATUS_JSON_CONFIG_LAYER_STATUS="${CONFIG_LAYER_STATUS}"
  export STATUS_JSON_CONFIG_LAYER_SUMMARY="${CONFIG_LAYER_SUMMARY}"
  export STATUS_JSON_LAUNCHD_LAYER_STATUS="${LAUNCHD_LAYER_STATUS}"
  export STATUS_JSON_LAUNCHD_LAYER_SUMMARY="${LAUNCHD_LAYER_SUMMARY}"
  export STATUS_JSON_LEDGER_LAYER_STATUS="${LEDGER_LAYER_STATUS}"
  export STATUS_JSON_LEDGER_LAYER_SUMMARY="${LEDGER_LAYER_SUMMARY}"

  local py
  py="$(find_python_bin)" || true
  if [[ -n "$py" ]]; then
    "$py" - <<'PY' || true
import json
import os

def env(name, default=""):
    return os.environ.get(name, default)

def env_int(name):
    value = env(name, "")
    if value.isdigit():
        return int(value)
    return None

state_json = env("STATUS_JSON_STATE_JSON_FILE", "")
metrics_jsonl = env("STATUS_JSON_METRICS_JSONL_FILE", "")
log_health = {
    "tail_lines": env_int("STATUS_JSON_LOG_HEALTH_TAIL_LINES"),
    "pattern": env("STATUS_JSON_LOG_HEALTH_PATTERN", ""),
    "errors_stdout": env_int("STATUS_JSON_LOG_HEALTH_ERRORS_STDOUT"),
    "errors_stderr": env_int("STATUS_JSON_LOG_HEALTH_ERRORS_STDERR"),
    "errors_launchd": env_int("STATUS_JSON_LOG_HEALTH_ERRORS_LAUNCHD"),
    "errors_total": env_int("STATUS_JSON_LOG_HEALTH_ERRORS_TOTAL"),
}
data = {}
if state_json and os.path.isfile(state_json):
    try:
        with open(state_json, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

phases = data.get("phases") or {}
pipeline_exit_reason = data.get("pipeline_exit_reason") or ""
failure_reason = data.get("failure_reason") or ""
schema_version = data.get("schema_version", "unknown")

total = 0
items = []
for name, value in phases.items():
    try:
        duration = int(value)
    except Exception:
        continue
    if duration < 0:
        continue
    total += duration
    items.append((name, duration))

width = 30
bars = []
if total > 0 and items:
    for name, duration in sorted(items, key=lambda x: x[1], reverse=True):
        ratio = duration / total if total else 0
        bar_len = int(round(width * ratio))
        if bar_len <= 0 and duration > 0:
            bar_len = 1
        if bar_len > width:
            bar_len = width
        bar = "#" * bar_len + "-" * (width - bar_len)
        percent = int(round(ratio * 100))
        bars.append({
            "name": name,
            "duration_sec": duration,
            "percent": percent,
            "bar": bar,
        })

reasons_raw = env("STATUS_JSON_HEALTH_REASONS", "")
health_reasons = [r for r in reasons_raw.split(",") if r] if reasons_raw else []

payload = {
    "status": env("STATUS_JSON_STATUS", "unknown"),
    "exit_code": env_int("STATUS_JSON_EXIT_CODE"),
    "schema_version": schema_version,
    "schema_version_expected": env("STATUS_JSON_SCHEMA_VERSION_EXPECTED", ""),
    "schema_warning": env("STATUS_JSON_SCHEMA_WARNING", ""),
    "last_run_iso": env("STATUS_JSON_LAST_RUN_ISO", "unknown"),
    "last_success_iso": env("STATUS_JSON_LAST_SUCCESS_ISO", "unknown"),
    "trigger_source": env("STATUS_JSON_TRIGGER_SOURCE", "unknown"),
    "run_id": env("STATUS_JSON_RUN_ID", ""),
    "checksum_status": env("STATUS_JSON_CHECKSUM_STATUS", "unknown"),
    "checksum_warning": env("STATUS_JSON_CHECKSUM_WARNING", ""),
    "age_sec": env_int("STATUS_JSON_AGE_SEC"),
    "stale": env("STATUS_JSON_STALE", "unknown"),
    "interval_min": env_int("STATUS_JSON_INTERVAL_MINUTES"),
    "launchd": env("STATUS_JSON_LAUNCHD", "unknown"),
    "health_score": env_int("STATUS_JSON_HEALTH_SCORE"),
    "health_level": env("STATUS_JSON_HEALTH_LEVEL", "unknown"),
    "health_reasons": health_reasons,
    "health_summary": env("STATUS_JSON_HEALTH_SUMMARY", ""),
    "metrics_jsonl_file": metrics_jsonl if metrics_jsonl else "",
    "log_health": log_health,
    "pipeline_exit_reason": pipeline_exit_reason,
    "failure_reason": failure_reason,
    "phases": phases,
    "phases_bar": bars,
    "state_layers": {
        "config": {
            "status": env("STATUS_JSON_CONFIG_LAYER_STATUS", "unknown"),
            "summary": env("STATUS_JSON_CONFIG_LAYER_SUMMARY", ""),
            "root_dir": env("STATUS_JSON_ROOT_DIR", ""),
            "log_dir": env("STATUS_JSON_LOG_DIR", ""),
            "state_dir": env("STATUS_JSON_STATE_DIR", ""),
            "interval_min": env_int("STATUS_JSON_INTERVAL_MINUTES"),
        },
        "launchd": {
            "status": env("STATUS_JSON_LAUNCHD_LAYER_STATUS", "unknown"),
            "summary": env("STATUS_JSON_LAUNCHD_LAYER_SUMMARY", ""),
            "label": env("STATUS_JSON_LAUNCHD_LABEL", ""),
        },
        "ledger": {
            "status": env("STATUS_JSON_LEDGER_LAYER_STATUS", "unknown"),
            "summary": env("STATUS_JSON_LEDGER_LAYER_SUMMARY", ""),
            "state_status": env("STATUS_JSON_STATUS", "unknown"),
            "last_success_iso": env("STATUS_JSON_LAST_SUCCESS_ISO", "unknown"),
            "failure_reason": failure_reason,
            "stale": env("STATUS_JSON_STALE", "unknown"),
        },
    },
}

print(json.dumps(payload, ensure_ascii=True, indent=2))
PY
    return 0
  fi

  cat <<JSON
{
  "status": "${status_value}",
  "exit_code": "${exit_value}",
  "schema_version": "unknown",
  "schema_version_expected": "${STATE_SCHEMA_VERSION_EXPECTED}",
  "schema_warning": "${SCHEMA_WARNING:-}",
  "last_run_iso": "${last_run_value}",
  "last_success_iso": "${last_success_value}",
  "trigger_source": "${trigger_source:-unknown}",
  "run_id": "${run_id:-}",
  "checksum_status": "${CHECKSUM_STATUS:-unknown}",
  "checksum_warning": "${CHECKSUM_WARNING:-}",
  "age_sec": "${AGE_SEC:-}",
  "stale": "${STALE}",
  "interval_min": "${NOTES_SNAPSHOT_INTERVAL_MINUTES}",
  "launchd": "${LAUNCHD_STATE}",
  "health_score": "${HEALTH_SCORE:-0}",
  "health_level": "${HEALTH_LEVEL:-unknown}",
  "health_reasons": "${reasons_csv}",
  "health_summary": "${HEALTH_SUMMARY}",
  "metrics_jsonl_file": "${METRICS_JSONL_FILE}",
  "log_health": {
    "tail_lines": "${TAIL_LINES}",
    "pattern": "${NOTES_SNAPSHOT_LOG_HEALTH_PATTERN}",
    "errors_stdout": "${LOG_HEALTH_ERRORS_STDOUT:-0}",
    "errors_stderr": "${LOG_HEALTH_ERRORS_STDERR:-0}",
    "errors_launchd": "${LOG_HEALTH_ERRORS_LAUNCHD:-0}",
    "errors_total": "${LOG_HEALTH_ERRORS_TOTAL:-0}"
  },
  "failure_reason": "${failure_reason:-}",
  "state_layers": {
    "config": {
      "status": "${CONFIG_LAYER_STATUS}",
      "summary": "${CONFIG_LAYER_SUMMARY}",
      "root_dir": "${NOTES_SNAPSHOT_ROOT_DIR}",
      "log_dir": "${NOTES_SNAPSHOT_LOG_DIR}",
      "state_dir": "${NOTES_SNAPSHOT_STATE_DIR}",
      "interval_min": "${NOTES_SNAPSHOT_INTERVAL_MINUTES}"
    },
    "launchd": {
      "status": "${LAUNCHD_LAYER_STATUS}",
      "summary": "${LAUNCHD_LAYER_SUMMARY}",
      "label": "${LAUNCHD_LABEL}"
    },
    "ledger": {
      "status": "${LEDGER_LAYER_STATUS}",
      "summary": "${LEDGER_LAYER_SUMMARY}",
      "state_status": "${status_value}",
      "last_success_iso": "${last_success_value}",
      "failure_reason": "${failure_reason:-}",
      "stale": "${STALE}"
    }
  }
}
JSON
}

# ------------------------------
# Compute summary
# ------------------------------
state_load_state_prefer_json "$STATE_FILE" "$LAST_RUN_FILE" "$LAST_SUCCESS_FILE" "$STATE_JSON_FILE"

NOW_EPOCH="$(date +%s)"
STALE="unknown"
if [[ -n "${last_success_epoch:-}" ]]; then
  AGE_SEC=$(( NOW_EPOCH - last_success_epoch ))
  if [[ "$AGE_SEC" -gt "$NOTES_SNAPSHOT_STALE_THRESHOLD_SEC" ]]; then
    STALE="yes"
  else
    STALE="no"
  fi
fi

LAUNCHD_STATE="not_loaded"
if command -v launchctl >/dev/null 2>&1; then
  if launchctl print "gui/$(id -u)/${LAUNCHD_LABEL}" >/dev/null 2>&1; then
    LAUNCHD_STATE="loaded"
  else
    LAUNCHD_STATE="not_loaded"
  fi
fi

LOG_HEALTH_ERRORS_STDOUT=0
LOG_HEALTH_ERRORS_STDERR=0
LOG_HEALTH_ERRORS_LAUNCHD=0
LOG_HEALTH_ERRORS_TOTAL=0
read -r LOG_HEALTH_ERRORS_STDOUT LOG_HEALTH_ERRORS_STDERR LOG_HEALTH_ERRORS_LAUNCHD < <(log_health_counts "$NOTES_SNAPSHOT_LOG_DIR" "$TAIL_LINES" "$NOTES_SNAPSHOT_LOG_HEALTH_PATTERN")
LOG_HEALTH_ERRORS_TOTAL=$(( LOG_HEALTH_ERRORS_STDOUT + LOG_HEALTH_ERRORS_STDERR + LOG_HEALTH_ERRORS_LAUNCHD ))

CHECKSUM_STATUS="unknown"
CHECKSUM_WARNING=""
verify_state_checksum() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    return 0
  fi
  local py
  py="$(find_python_bin)" || return 0
  local result
  result="$("$py" - "$file" <<'PY' || true
import hashlib
import json
import sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    print("error:read_failed")
    sys.exit(0)

checksum = data.get("checksum")
data.pop("checksum", None)
canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
calc = hashlib.sha256(canonical).hexdigest()
if checksum is None:
    print("missing:")
elif checksum == calc:
    print("ok:")
else:
    print(f"mismatch:{checksum}")
PY
)"
  if [[ -z "$result" ]]; then
    return 0
  fi
  local checksum_status_local="${result%%:*}"
  local detail="${result#*:}"
  CHECKSUM_STATUS="$checksum_status_local"
  case "$checksum_status_local" in
    mismatch)
      CHECKSUM_WARNING="state.json checksum mismatch"
      ;;
    missing)
      CHECKSUM_WARNING="state.json checksum missing"
      ;;
    error)
      CHECKSUM_WARNING="state.json checksum read error"
      ;;
  esac
}
verify_state_checksum "$STATE_JSON_FILE"

SCHEMA_WARNING=""
if [[ -n "${schema_version:-}" ]]; then
  if [[ "$schema_version" != "$STATE_SCHEMA_VERSION_EXPECTED" ]]; then
    SCHEMA_WARNING="schema_version mismatch (expected ${STATE_SCHEMA_VERSION_EXPECTED}, got ${schema_version})"
  fi
fi
if [[ -n "${state_json_warning:-}" ]]; then
  if [[ -n "$SCHEMA_WARNING" ]]; then
    SCHEMA_WARNING="${SCHEMA_WARNING}; ${state_json_warning}"
  else
    SCHEMA_WARNING="${state_json_warning}"
  fi
fi
if [[ -n "${CHECKSUM_WARNING:-}" ]]; then
  if [[ -n "$SCHEMA_WARNING" ]]; then
    SCHEMA_WARNING="${SCHEMA_WARNING}; ${CHECKSUM_WARNING}"
  else
    SCHEMA_WARNING="${CHECKSUM_WARNING}"
  fi
fi

AGE_SEC="${AGE_SEC:-}"
calc_health_score
derive_state_layers
derive_health_summary

if [[ "$MODE" == "json" ]]; then
  print_status_json "$STATE_JSON_FILE"
  exit 0
fi

# ------------------------------
# Brief mode
# ------------------------------
if [[ "$MODE" == "brief" ]]; then
  AGE_SEC=""
  if [[ -n "${last_success_epoch:-}" ]]; then
    AGE_SEC=$(( NOW_EPOCH - last_success_epoch ))
  fi
  printf 'status=%s last_run=%s last_success=%s age_sec=%s stale=%s interval_min=%s launchd=%s\n' \
    "${STATE_STATUS:-unknown}" \
    "${last_run_iso:-unknown}" \
    "${last_success_iso:-unknown}" \
    "${AGE_SEC:-unknown}" \
    "$STALE" \
    "$NOTES_SNAPSHOT_INTERVAL_MINUTES" \
    "$LAUNCHD_STATE"
  if [[ -n "$AGE_SEC" ]]; then
    INTERVAL_SEC=$(( NOTES_SNAPSHOT_INTERVAL_MINUTES * 60 ))
    if [[ "$AGE_SEC" -le "$INTERVAL_SEC" ]]; then
      echo "OK: last success within 1 interval"
    elif [[ "$AGE_SEC" -le $(( INTERVAL_SEC * 2 )) ]]; then
      echo "WARN: last success older than 1 interval (sleep can cause this)"
      echo "NEXT: ./notesctl run"
    elif [[ "$AGE_SEC" -le "$NOTES_SNAPSHOT_STALE_THRESHOLD_SEC" ]]; then
      echo "WARN: last success getting stale"
      echo "NEXT: ./notesctl ensure && ./notesctl run"
    else
      echo "FAIL: last success stale"
      echo "NEXT: ./notesctl self-heal"
    fi
  fi
  exit 0
fi

# ------------------------------
# Launchd status
# ------------------------------
if command -v launchctl >/dev/null 2>&1; then
  echo "Launchd"
  launchctl print "gui/$(id -u)/${LAUNCHD_LABEL}" 2>/dev/null | \
    grep -E 'state =|path =|last exit|run interval|run count' || true
  echo ""
fi

# ------------------------------
# Summary first
# ------------------------------
if [[ -f "$SUMMARY_FILE" ]]; then
  echo "Summary"
  cat "$SUMMARY_FILE"
  echo ""
fi

if [[ "$MODE" == "full" || "$MODE" == "verbose" ]]; then
  print_schema_info "$STATE_JSON_FILE"
  print_metrics_jsonl_summary "$METRICS_JSONL_FILE"
  print_health_block
  print_state_layers_block
  print_phases_bar_from_json "$STATE_JSON_FILE"
  print_phases_from_json "$STATE_JSON_FILE"
  print_pipeline_exit_reason "$STATE_JSON_FILE"
fi

# ------------------------------
# State summary
# ------------------------------
print_kv_file "State" "$STATE_FILE"
print_kv_file "Last Run" "$LAST_RUN_FILE"
print_kv_file "Last Success" "$LAST_SUCCESS_FILE"

# ------------------------------
# Staleness check
# ------------------------------
if [[ -n "${last_success_epoch:-}" ]]; then
  AGE_SEC=$(( NOW_EPOCH - last_success_epoch ))
  if [[ "$AGE_SEC" -gt "$NOTES_SNAPSHOT_STALE_THRESHOLD_SEC" ]]; then
    echo "WARN: last success is stale (${AGE_SEC}s > ${NOTES_SNAPSHOT_STALE_THRESHOLD_SEC}s)"
    echo ""
  fi
fi

if [[ -n "$SCHEMA_WARNING" ]]; then
  echo "WARN: ${SCHEMA_WARNING}"
  echo ""
fi

# ------------------------------
# JSON (verbose only)
# ------------------------------
if [[ -f "$STATE_JSON_FILE" ]] && [[ "$MODE" == "verbose" ]]; then
  print_phases_from_json "$STATE_JSON_FILE"
  print_pipeline_exit_reason "$STATE_JSON_FILE"
  echo "State JSON"
  cat "$STATE_JSON_FILE"
  echo ""
fi

# ------------------------------
# Vendor info
# ------------------------------
if [[ -f "$VENDOR_INFO" ]]; then
  echo "Vendor"
  cat "$VENDOR_INFO"
  echo ""
fi

# ------------------------------
# Logs (verbose only)
# ------------------------------
if [[ "$MODE" == "verbose" ]]; then
  if [[ -f "$NOTES_SNAPSHOT_LOG_DIR/stdout.log" ]]; then
    echo "stdout (tail)"
    tail -n "$TAIL_LINES" "$NOTES_SNAPSHOT_LOG_DIR/stdout.log"
    echo ""
  fi

  if [[ -f "$NOTES_SNAPSHOT_LOG_DIR/stderr.log" ]]; then
    echo "stderr (tail)"
    tail -n "$TAIL_LINES" "$NOTES_SNAPSHOT_LOG_DIR/stderr.log"
    echo ""
  fi
fi

# ------------------------------
# Self-help
# ------------------------------
echo "Self-Help"
if [[ ! -f "$VENDOR_INFO" ]]; then
  echo " - vendor missing or VENDOR_INFO missing: run ./notesctl update-vendor (first run generates VENDOR_INFO)"
fi
if [[ "$LAUNCHD_STATE" == "not_loaded" ]]; then
  echo " - launchd not loaded: run ./notesctl install --minutes 30 --load"
fi
if [[ "$STALE" == "yes" ]]; then
  echo " - last success stale: run ./notesctl run"
elif [[ "$LEDGER_LAYER_STATUS" == "needs_first_run" ]]; then
  echo " - no successful snapshot yet: run ./notesctl run --no-status"
fi
