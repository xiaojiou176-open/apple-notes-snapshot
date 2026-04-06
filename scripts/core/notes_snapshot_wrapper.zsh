#!/bin/zsh
set -euo pipefail

# ------------------------------
# Paths
# ------------------------------
SCRIPT_DIR="${0:A:h}"
REPO_ROOT="${NOTES_SNAPSHOT_REPO_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
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

# ------------------------------
# Defaults
# ------------------------------
STATE_SCHEMA_VERSION="1"

validate_abs_path "NOTES_SNAPSHOT_ROOT_DIR" "$NOTES_SNAPSHOT_ROOT_DIR"
validate_abs_path "NOTES_SNAPSHOT_DIR" "$NOTES_SNAPSHOT_DIR"
validate_abs_path "NOTES_SNAPSHOT_LOG_DIR" "$NOTES_SNAPSHOT_LOG_DIR"
validate_abs_path "NOTES_SNAPSHOT_LOCK_DIR" "$NOTES_SNAPSHOT_LOCK_DIR"
validate_abs_path "NOTES_SNAPSHOT_LOCK_FILE" "$NOTES_SNAPSHOT_LOCK_FILE"
validate_abs_path "NOTES_SNAPSHOT_STATE_DIR" "$NOTES_SNAPSHOT_STATE_DIR"
validate_uint "NOTES_SNAPSHOT_LOG_MAX_BYTES" "$NOTES_SNAPSHOT_LOG_MAX_BYTES"
validate_uint "NOTES_SNAPSHOT_LOG_BACKUPS" "$NOTES_SNAPSHOT_LOG_BACKUPS"
validate_uint "NOTES_SNAPSHOT_STALE_THRESHOLD_SEC" "$NOTES_SNAPSHOT_STALE_THRESHOLD_SEC"
validate_uint "NOTES_SNAPSHOT_WRITE_STATE_JSON" "$NOTES_SNAPSHOT_WRITE_STATE_JSON"
validate_uint "NOTES_SNAPSHOT_WRITE_SUMMARY" "$NOTES_SNAPSHOT_WRITE_SUMMARY"
validate_uint "NOTES_SNAPSHOT_PREFER_STATE_JSON" "$NOTES_SNAPSHOT_PREFER_STATE_JSON"
validate_uint "NOTES_SNAPSHOT_LOCK_TTL_SEC" "$NOTES_SNAPSHOT_LOCK_TTL_SEC"
if [[ "$NOTES_SNAPSHOT_LOG_MAX_BYTES" -le 0 ]]; then
  echo "NOTES_SNAPSHOT_LOG_MAX_BYTES must be > 0" >&2
  exit 1
fi
if [[ "$NOTES_SNAPSHOT_LOG_BACKUPS" -lt 1 ]]; then
  echo "NOTES_SNAPSHOT_LOG_BACKUPS must be >= 1" >&2
  exit 1
fi
if [[ "$NOTES_SNAPSHOT_WRITE_STATE_JSON" -ne 0 && "$NOTES_SNAPSHOT_WRITE_STATE_JSON" -ne 1 ]]; then
  echo "NOTES_SNAPSHOT_WRITE_STATE_JSON must be 0 or 1" >&2
  exit 1
fi
if [[ "$NOTES_SNAPSHOT_WRITE_SUMMARY" -ne 0 && "$NOTES_SNAPSHOT_WRITE_SUMMARY" -ne 1 ]]; then
  echo "NOTES_SNAPSHOT_WRITE_SUMMARY must be 0 or 1" >&2
  exit 1
fi
if [[ "$NOTES_SNAPSHOT_PREFER_STATE_JSON" -ne 0 && "$NOTES_SNAPSHOT_PREFER_STATE_JSON" -ne 1 ]]; then
  echo "NOTES_SNAPSHOT_PREFER_STATE_JSON must be 0 or 1" >&2
  exit 1
fi
if [[ -n "${NOTES_SNAPSHOT_TIMEOUT_SEC}" ]]; then
  validate_uint "NOTES_SNAPSHOT_TIMEOUT_SEC" "$NOTES_SNAPSHOT_TIMEOUT_SEC"
fi

# ------------------------------
# Prepare
# ------------------------------
ensure_dir "$NOTES_SNAPSHOT_ROOT_DIR"
ensure_dir "$NOTES_SNAPSHOT_LOG_DIR"
ensure_dir "$NOTES_SNAPSHOT_STATE_DIR"
ensure_dir "${NOTES_SNAPSHOT_LOCK_FILE:h}"
if [[ "$NOTES_SNAPSHOT_LOG_ROTATE_MODE" != "copytruncate" && "$NOTES_SNAPSHOT_LOG_ROTATE_MODE" != "rename" ]]; then
  echo "NOTES_SNAPSHOT_LOG_ROTATE_MODE must be copytruncate|rename" >&2
  exit 1
fi
rotation_summary="$(rotate_files_summary \
  "$NOTES_SNAPSHOT_LOG_MAX_BYTES" \
  "$NOTES_SNAPSHOT_LOG_BACKUPS" \
  "$NOTES_SNAPSHOT_LOG_ROTATE_MODE" \
  "${NOTES_SNAPSHOT_LOG_DIR}/stdout.log" \
  "${NOTES_SNAPSHOT_LOG_DIR}/stderr.log" \
  "${NOTES_SNAPSHOT_LOG_DIR}/launchd.out.log" \
  "${NOTES_SNAPSHOT_LOG_DIR}/launchd.err.log" \
  "${NOTES_SNAPSHOT_LOG_DIR}/structured.jsonl")"
log_line "$rotation_summary" >> "$NOTES_SNAPSHOT_LOG_DIR/stdout.log"
metrics_rotation_summary="$(rotate_files_summary \
  "$NOTES_SNAPSHOT_LOG_MAX_BYTES" \
  "$NOTES_SNAPSHOT_LOG_BACKUPS" \
  "$NOTES_SNAPSHOT_LOG_ROTATE_MODE" \
  "${NOTES_SNAPSHOT_STATE_DIR}/metrics.jsonl" \
  "${NOTES_SNAPSHOT_STATE_DIR}/phase_metrics.log")"
log_line "$metrics_rotation_summary" >> "$NOTES_SNAPSHOT_LOG_DIR/stdout.log"

# ------------------------------
# State
# ------------------------------
state_set_paths "$NOTES_SNAPSHOT_STATE_DIR"
FINALIZED=0
LAST_SUCCESS_EPOCH=""
LAST_SUCCESS_ISO=""
RUNTIME_EXPORTER_SCRIPT=""
RUNTIME_EXPORTER_PATH="$PATH"
EXPORTER_SCRIPT=""
LOCK_MODE="dir"
LOCK_ACQUIRED=0
FAILURE_REASON=""
TIMEOUT_USED=0
RUN_ID=""
TRIGGER_SOURCE="${NOTES_SNAPSHOT_TRIGGER_SOURCE:-}"
if [[ -z "$TRIGGER_SOURCE" ]]; then
  if [[ -n "${LAUNCHD_JOB_LABEL:-}" || -n "${LAUNCHD_SESSION_TYPE:-}" ]]; then
    TRIGGER_SOURCE="launchd"
  else
    TRIGGER_SOURCE="manual"
  fi
fi

finalize_state() {
  local run_status="$1"
  local exit_code="$2"
  local end_epoch="${3:-}"
  local end_iso="${4:-}"
  local duration_sec="${5:-}"
  local start_epoch_local start_iso_local

  start_epoch_local="${START_EPOCH:-$(date +%s)}"
  start_iso_local="${START_ISO:-$(date -u '+%Y-%m-%dT%H:%M:%SZ')}"
  if [[ -z "$end_epoch" ]]; then
    end_epoch="$(date +%s)"
  fi
  if [[ -z "$end_iso" ]]; then
    end_iso="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  fi
  if [[ -z "$duration_sec" ]]; then
    duration_sec=$(( end_epoch - start_epoch_local ))
  fi

  if [[ -z "$LAST_SUCCESS_ISO" ]] && [[ -f "$LAST_SUCCESS_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$LAST_SUCCESS_FILE"
    LAST_SUCCESS_ISO="${last_success_iso:-}"
    if [[ -z "$LAST_SUCCESS_EPOCH" ]]; then
      LAST_SUCCESS_EPOCH="${last_success_epoch:-}"
    fi
  fi

  local phases_json=""
  phases_json="$(state_build_phases_json "$METRICS_FILE")"
  local phases_summary=""
  phases_summary="$(state_build_phases_summary "$METRICS_FILE")"
  local pipeline_exit_reason=""
  pipeline_exit_reason="$(state_read_single_line "$PIPELINE_EXIT_REASON_FILE")"

  state_write_state_bundle "$run_status" "$exit_code" "$duration_sec" \
    "$start_epoch_local" "$start_iso_local" "$end_epoch" "$end_iso" \
    "$NOTES_SNAPSHOT_ROOT_DIR" "$EXPORTER_SCRIPT" "$$" "${LAST_SUCCESS_ISO:-}" \
    "$phases_json" "$phases_summary" "$pipeline_exit_reason" "${LAST_SUCCESS_EPOCH:-}" "${FAILURE_REASON:-}" "$RUN_ID" "$TRIGGER_SOURCE"

  local phases_line=""
  if [[ -n "$phases_json" ]]; then
    phases_line=$', '"$(state_json_field_raw "phases" "$phases_json")"
  fi
  local pipeline_line=""
  if [[ -n "$pipeline_exit_reason" ]]; then
    pipeline_line=$', '"$(state_json_field_string "pipeline_exit_reason" "$pipeline_exit_reason")"
  fi
  local failure_line=""
  if [[ -n "${FAILURE_REASON:-}" ]]; then
    failure_line=$', '"$(state_json_field_string "failure_reason" "$FAILURE_REASON")"
  fi
  local end_line=""
  end_line="{"
  end_line+=$(state_json_field_string "event" "run_end")
  end_line+=", "$(state_json_field_number "schema_version" "$STATE_SCHEMA_VERSION")
  end_line+=", "$(state_json_field_string "status" "$run_status")
  end_line+=", "$(state_json_field_number "exit_code" "$exit_code")
  end_line+=", "$(state_json_field_number "duration_sec" "$duration_sec")
  end_line+=", "$(state_json_field_number "start_epoch" "$start_epoch_local")
  end_line+=", "$(state_json_field_number "end_epoch" "$end_epoch")
  end_line+=", "$(state_json_field_string "end_iso" "$end_iso")
  end_line+=", "$(state_json_field_string "run_id" "$RUN_ID")
  end_line+=", "$(state_json_field_string "trigger_source" "$TRIGGER_SOURCE")
  end_line+="$phases_line"
  end_line+="$pipeline_line"
  end_line+="$failure_line"
  end_line+="}"
  state_write_metrics_jsonl "$end_line"
}

cleanup() {
  local exit_code="$?"
  if [[ "$FINALIZED" -eq 0 ]]; then
    finalize_state "aborted" "$exit_code"
  fi
  if [[ "$LOCK_ACQUIRED" -eq 1 ]]; then
    if [[ "$LOCK_MODE" == "flock" ]]; then
      exec 200>&- || true
    else
      "$RMDIR_BIN" -- "$NOTES_SNAPSHOT_LOCK_DIR" 2>/dev/null || true
    fi
  fi
}

on_signal() {
  local sig="$1"
  log_line "received signal: ${sig}" >> "$NOTES_SNAPSHOT_LOG_DIR/stderr.log"
  exit 130
}

trap 'on_signal INT' INT
trap 'on_signal TERM' TERM
trap 'cleanup' EXIT

lock_dir_mtime_epoch() {
  if command -v stat >/dev/null 2>&1; then
    if stat -f %m "$NOTES_SNAPSHOT_LOCK_DIR" >/dev/null 2>&1; then
      stat -f %m "$NOTES_SNAPSHOT_LOCK_DIR"
      return 0
    fi
    if stat -c %Y "$NOTES_SNAPSHOT_LOCK_DIR" >/dev/null 2>&1; then
      stat -c %Y "$NOTES_SNAPSHOT_LOCK_DIR"
      return 0
    fi
  fi
  return 1
}

if command -v flock >/dev/null 2>&1; then
  LOCK_MODE="flock"
  exec 200>"$NOTES_SNAPSHOT_LOCK_FILE"
  if ! flock -n 200; then
    log_line "flock busy, skip" >> "$NOTES_SNAPSHOT_LOG_DIR/stderr.log"
    FINALIZED=1
    exit 0
  fi
  LOCK_ACQUIRED=1
else
  if ! "$MKDIR_BIN" -- "$NOTES_SNAPSHOT_LOCK_DIR" 2>/dev/null; then
    if [[ -f "$STATE_FILE" ]]; then
      state_load_kv_file "$STATE_FILE"
      if [[ "${STATE_STATUS:-}" == "running" ]] && [[ -n "${pid:-}" ]]; then
        if ps -p "$pid" >/dev/null 2>&1; then
          log_line "notes snapshot already running (pid=$pid), skip" >> "$NOTES_SNAPSHOT_LOG_DIR/stdout.log"
          FINALIZED=1
          exit 0
        fi
      fi
    fi
    if [[ "$NOTES_SNAPSHOT_LOCK_TTL_SEC" -gt 0 ]]; then
      LOCK_MTIME_EPOCH="$(lock_dir_mtime_epoch || true)"
      if [[ -n "$LOCK_MTIME_EPOCH" ]]; then
        LOCK_NOW_EPOCH="$(date +%s)"
        LOCK_AGE_SEC=$(( LOCK_NOW_EPOCH - LOCK_MTIME_EPOCH ))
        if [[ "$LOCK_AGE_SEC" -lt "$NOTES_SNAPSHOT_LOCK_TTL_SEC" ]]; then
          log_line "lock dir present (age=${LOCK_AGE_SEC}s < ttl=${NOTES_SNAPSHOT_LOCK_TTL_SEC}s), skip" >> "$NOTES_SNAPSHOT_LOG_DIR/stderr.log"
          FINALIZED=1
          exit 0
        fi
        log_line "lock dir stale (age=${LOCK_AGE_SEC}s >= ttl=${NOTES_SNAPSHOT_LOCK_TTL_SEC}s), clearing" >> "$NOTES_SNAPSHOT_LOG_DIR/stderr.log"
      fi
    fi
    log_line "stale lock detected, clearing" >> "$NOTES_SNAPSHOT_LOG_DIR/stderr.log"
    "$RMDIR_BIN" -- "$NOTES_SNAPSHOT_LOCK_DIR" 2>/dev/null || true
    if ! "$MKDIR_BIN" -- "$NOTES_SNAPSHOT_LOCK_DIR" 2>/dev/null; then
      log_line "failed to acquire lock after cleanup, skip" >> "$NOTES_SNAPSHOT_LOG_DIR/stderr.log"
      FINALIZED=1
      exit 1
    fi
  fi
  LOCK_ACQUIRED=1
fi

EXPORTER_SCRIPT="${NOTES_SNAPSHOT_DIR}/exportnotes.zsh"
if [[ ! -x "$EXPORTER_SCRIPT" ]]; then
  FAILURE_REASON="exporter_missing"
  log_line "missing exporter script: $EXPORTER_SCRIPT" >> "$NOTES_SNAPSHOT_LOG_DIR/stderr.log"
  exit 1
fi

prepare_runtime_exporter_surface() {
  local source_dir="$NOTES_SNAPSHOT_DIR"
  local runtime_dir="${NOTES_SNAPSHOT_VENDOR_RUNTIME_ROOT}"
  local runtime_base="${runtime_dir:h}"
  local shim_dir="${runtime_base}/bin"
  local py_bin=""

  py_bin="$(state_find_python 2>/dev/null)" || py_bin=""
  if [[ "$source_dir" != *" "* ]] && command -v python >/dev/null 2>&1; then
    RUNTIME_EXPORTER_SCRIPT="$EXPORTER_SCRIPT"
    RUNTIME_EXPORTER_PATH="$PATH"
    return 0
  fi

  ensure_dir "$runtime_base"
  /bin/rm -rf -- "$runtime_dir"
  ensure_dir "$runtime_dir"
  /bin/cp -R "$source_dir/." "$runtime_dir/"
  /bin/chmod +x "$runtime_dir/exportnotes.zsh" 2>/dev/null || true

  RUNTIME_EXPORTER_SCRIPT="${runtime_dir}/exportnotes.zsh"
  RUNTIME_EXPORTER_PATH="$PATH"

  if [[ -n "$py_bin" ]]; then
    ensure_dir "$shim_dir"
    /bin/cat > "${shim_dir}/python" <<SH
#!/bin/sh
exec "${py_bin}" "\$@"
SH
    /bin/chmod +x "${shim_dir}/python"
    RUNTIME_EXPORTER_PATH="${shim_dir}:${PATH}"
  fi
}

prepare_runtime_exporter_surface

START_EPOCH="$(date +%s)"
START_ISO="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
RUN_ID="$(date -u '+%Y%m%dT%H%M%SZ')-${$}-${RANDOM}"
export NOTES_SNAPSHOT_RUN_ID="$RUN_ID"
export NOTES_SNAPSHOT_RUN_PID="$$"
export NOTES_SNAPSHOT_TRIGGER_SOURCE="$TRIGGER_SOURCE"

state_write_env_file "$LAST_RUN_FILE" \
  "$(state_kv_line last_run_epoch "$START_EPOCH")" \
  "$(state_kv_line last_run_iso "$START_ISO")" \
  "$(state_kv_line pid "$$")"

state_write_env_file "$STATE_FILE" \
  "$(state_kv_line status "running")" \
  "$(state_kv_line start_epoch "$START_EPOCH")" \
  "$(state_kv_line start_iso "$START_ISO")" \
  "$(state_kv_line pid "$$")" \
  "$(state_kv_line root_dir "$NOTES_SNAPSHOT_ROOT_DIR")" \
  "$(state_kv_line exporter_script "$EXPORTER_SCRIPT")" \
  "$(state_kv_line run_id "$RUN_ID")"

start_line="{"
start_line+=$(state_json_field_string "event" "run_start")
start_line+=", "$(state_json_field_number "schema_version" "$STATE_SCHEMA_VERSION")
start_line+=", "$(state_json_field_number "start_epoch" "$START_EPOCH")
start_line+=", "$(state_json_field_string "start_iso" "$START_ISO")
start_line+=", "$(state_json_field_number "pid" "$$")
start_line+=", "$(state_json_field_string "root_dir" "$NOTES_SNAPSHOT_ROOT_DIR")
start_line+=", "$(state_json_field_string "run_id" "$RUN_ID")
start_line+=", "$(state_json_field_string "trigger_source" "$TRIGGER_SOURCE")
start_line+="}"
state_write_metrics_jsonl "$start_line"

# ------------------------------
# Metrics
# ------------------------------
: > "$METRICS_FILE"
export NOTES_EXPORT_METRICS_FILE="$METRICS_FILE"
: > "$PIPELINE_EXIT_REASON_FILE"
export NOTES_EXPORT_PIPELINE_EXIT_REASON_FILE="$PIPELINE_EXIT_REASON_FILE"

# ------------------------------
# Build args
# ------------------------------
EXPORTER_ARGS=()
if [[ -n "${NOTES_SNAPSHOT_ARGS:-}" ]]; then
  EXPORTER_ARGS=(${(z)NOTES_SNAPSHOT_ARGS})
fi

CLI_ARGS=("$@")

# ------------------------------
# Run
# ------------------------------
log_line "start export" >> "$NOTES_SNAPSHOT_LOG_DIR/stdout.log"
set +e
if [[ -n "${NOTES_SNAPSHOT_TIMEOUT_SEC}" ]]; then
  if command -v gtimeout >/dev/null 2>&1; then
    TIMEOUT_USED=1
    PATH="$RUNTIME_EXPORTER_PATH" gtimeout "$NOTES_SNAPSHOT_TIMEOUT_SEC" \
      "$RUNTIME_EXPORTER_SCRIPT" --root-dir "$NOTES_SNAPSHOT_ROOT_DIR" "${EXPORTER_ARGS[@]}" "${CLI_ARGS[@]}" \
      >> "$NOTES_SNAPSHOT_LOG_DIR/stdout.log" 2>> "$NOTES_SNAPSHOT_LOG_DIR/stderr.log"
  elif command -v timeout >/dev/null 2>&1; then
    TIMEOUT_USED=1
    PATH="$RUNTIME_EXPORTER_PATH" timeout "$NOTES_SNAPSHOT_TIMEOUT_SEC" \
      "$RUNTIME_EXPORTER_SCRIPT" --root-dir "$NOTES_SNAPSHOT_ROOT_DIR" "${EXPORTER_ARGS[@]}" "${CLI_ARGS[@]}" \
      >> "$NOTES_SNAPSHOT_LOG_DIR/stdout.log" 2>> "$NOTES_SNAPSHOT_LOG_DIR/stderr.log"
  else
    log_line "timeout requested but no timeout tool found; running without timeout" >> "$NOTES_SNAPSHOT_LOG_DIR/stderr.log"
    PATH="$RUNTIME_EXPORTER_PATH" "$RUNTIME_EXPORTER_SCRIPT" --root-dir "$NOTES_SNAPSHOT_ROOT_DIR" "${EXPORTER_ARGS[@]}" "${CLI_ARGS[@]}" \
      >> "$NOTES_SNAPSHOT_LOG_DIR/stdout.log" 2>> "$NOTES_SNAPSHOT_LOG_DIR/stderr.log"
  fi
else
  PATH="$RUNTIME_EXPORTER_PATH" "$RUNTIME_EXPORTER_SCRIPT" --root-dir "$NOTES_SNAPSHOT_ROOT_DIR" "${EXPORTER_ARGS[@]}" "${CLI_ARGS[@]}" \
    >> "$NOTES_SNAPSHOT_LOG_DIR/stdout.log" 2>> "$NOTES_SNAPSHOT_LOG_DIR/stderr.log"
fi
EXIT_CODE="$?"
set -e

if [[ "$EXIT_CODE" -eq 0 ]]; then
  FAILURE_REASON=""
fi

if [[ "$EXIT_CODE" -ne 0 && -z "$FAILURE_REASON" ]]; then
	  if [[ "$TIMEOUT_USED" -eq 1 ]] && [[ "$EXIT_CODE" -eq 124 || "$EXIT_CODE" -eq 137 ]]; then
	    FAILURE_REASON="timeout"
  elif [[ "$EXIT_CODE" -eq 126 ]]; then
    FAILURE_REASON="permission"
  elif [[ "$EXIT_CODE" -eq 127 ]]; then
    FAILURE_REASON="exporter_missing"
  else
    local err_tail=""
    if [[ -f "$NOTES_SNAPSHOT_LOG_DIR/stderr.log" ]]; then
      err_tail="$(tail -n "$NOTES_SNAPSHOT_TAIL_LINES" "$NOTES_SNAPSHOT_LOG_DIR/stderr.log" || true)"
fi
    if [[ -n "$err_tail" ]]; then
      if echo "$err_tail" | grep -E -i 'not authorized to send apple events|not permitted to send apple events|apple events.*not authorized|operation not permitted' >/dev/null 2>&1; then
        FAILURE_REASON="tcc_denied"
      elif echo "$err_tail" | grep -E -i "can't get application \"notes\"|application \"notes\" is not running|notes got an error" >/dev/null 2>&1; then
        FAILURE_REASON="notes_not_accessible"
      elif echo "$err_tail" | grep -E -i 'osascript|applescript' >/dev/null 2>&1; then
        FAILURE_REASON="osascript_fail"
      fi
    fi
  fi
fi

END_EPOCH="$(date +%s)"
END_ISO="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
DURATION_SEC=$(( END_EPOCH - START_EPOCH ))

if [[ "$EXIT_CODE" -eq 0 ]]; then
  LAST_SUCCESS_EPOCH="$END_EPOCH"
  LAST_SUCCESS_ISO="$END_ISO"
  state_write_env_file "$LAST_SUCCESS_FILE" \
    "$(state_kv_line last_success_epoch "$END_EPOCH")" \
    "$(state_kv_line last_success_iso "$END_ISO")"
  RUN_STATUS="success"
else
  RUN_STATUS="failed"
fi

finalize_state "$RUN_STATUS" "$EXIT_CODE" "$END_EPOCH" "$END_ISO" "$DURATION_SEC"
FINALIZED=1

log_line "end export (status=$RUN_STATUS, exit=$EXIT_CODE, duration=${DURATION_SEC}s)" >> "$NOTES_SNAPSHOT_LOG_DIR/stdout.log"
exit "$EXIT_CODE"
