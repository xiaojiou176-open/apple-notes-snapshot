#!/bin/zsh

# ------------------------------
# State helpers (sourced)
# ------------------------------
state_mktemp() {
  if command -v mktemp >/dev/null 2>&1; then
    mktemp
    return $?
  fi
  if [[ -x /usr/bin/mktemp ]]; then
    /usr/bin/mktemp
    return $?
  fi
  return 1
}

state_rm() {
  if [[ -x /bin/rm ]]; then
    /bin/rm -f -- "$@"
    return 0
  fi
  rm -f -- "$@" 2>/dev/null || true
}

state_set_paths() {
  local state_dir="${1:-${NOTES_SNAPSHOT_STATE_DIR:-}}"
  if [[ -z "$state_dir" ]]; then
    echo "missing NOTES_SNAPSHOT_STATE_DIR for state_set_paths" >&2
    exit 1
  fi

  STATE_FILE="${state_dir}/state.env"
  LAST_RUN_FILE="${state_dir}/last_run.env"
  LAST_SUCCESS_FILE="${state_dir}/last_success.env"
  STATE_JSON_FILE="${state_dir}/state.json"
  SUMMARY_FILE="${state_dir}/summary.txt"
  METRICS_FILE="${state_dir}/phase_metrics.log"
  METRICS_JSONL_FILE="${state_dir}/metrics.jsonl"
  PIPELINE_EXIT_REASON_FILE="${state_dir}/pipeline_exit_reason.txt"
}

state_load_kv_file() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    return 0
  fi

  local line key raw decoded
  while IFS= read -r line; do
    if [[ -z "$line" || "$line" != *=* ]]; then
      continue
    fi
    key="${line%%=*}"
    raw="${line#*=}"
    decoded=""
    eval "decoded=${raw}"
    case "$key" in
      status)
        STATE_STATUS="$decoded"
        ;;
      *)
        eval "${key}=\${decoded}"
        ;;
    esac
  done < "$file"
}

state_kv_line() {
  local key="$1"
  local value="$2"
  printf '%s=%q' "$key" "$value"
}

state_write_env_file() {
  local path="$1"
  shift
  local tmp="${path}.tmp.$$"
  : > "$tmp"
  for line in "$@"; do
    printf '%s\n' "$line" >> "$tmp"
  done
  mv -f -- "$tmp" "$path"
}

state_json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  printf '%s' "$value"
}

state_json_field_string() {
  local key="$1"
  local value="$2"
  printf '"%s":"%s"' "$key" "$(state_json_escape "$value")"
}

state_json_field_number() {
  local key="$1"
  local value="$2"
  printf '"%s":%s' "$key" "$value"
}

state_json_field_raw() {
  local key="$1"
  local value="$2"
  printf '"%s":%s' "$key" "$value"
}

state_build_phases_json() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    return 0
  fi

  local json="{"
  local first=1
  local line
  while IFS= read -r line; do
    local phase=""
    local duration=""
    if [[ "$line" == phase=* ]]; then
      phase="${line#phase=}"
      phase="${phase%% *}"
    fi
    if [[ "$line" == *"duration_sec="* ]]; then
      duration="${line##*duration_sec=}"
      duration="${duration%% *}"
    fi
    if [[ -z "$phase" || -z "$duration" ]]; then
      continue
    fi
    if [[ ! "$duration" =~ ^[0-9]+$ ]]; then
      continue
    fi
    if [[ "$first" -eq 0 ]]; then
      json+=", "
    fi
    json+="\"$(state_json_escape "$phase")\": $duration"
    first=0
  done < "$path"

  if [[ "$first" -eq 1 ]]; then
    return 0
  fi

  json+="}"
  printf '%s' "$json"
}

state_build_phases_summary() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    return 0
  fi

  local summary=""
  local first=1
  local line
  while IFS= read -r line; do
    local phase=""
    local duration=""
    if [[ "$line" == phase=* ]]; then
      phase="${line#phase=}"
      phase="${phase%% *}"
    fi
    if [[ "$line" == *"duration_sec="* ]]; then
      duration="${line##*duration_sec=}"
      duration="${duration%% *}"
    fi
    if [[ -z "$phase" || -z "$duration" ]]; then
      continue
    fi
    if [[ ! "$duration" =~ ^[0-9]+$ ]]; then
      continue
    fi
    if [[ "$first" -eq 0 ]]; then
      summary+=","
    fi
    summary+="${phase}:${duration}"
    first=0
  done < "$path"

  if [[ -z "$summary" ]]; then
    return 0
  fi
  printf '%s' "$summary"
}

state_read_single_line() {
  local path="$1"
  if [[ -f "$path" ]]; then
    local line=""
    IFS= read -r line < "$path" || true
    printf '%s' "$line"
  fi
}

# ------------------------------
# JSON read helpers
# ------------------------------
state_find_python() {
  if [[ -n "${NOTES_SNAPSHOT_PYTHON_BIN:-}" ]]; then
    if command -v "${NOTES_SNAPSHOT_PYTHON_BIN}" >/dev/null 2>&1; then
      command -v "${NOTES_SNAPSHOT_PYTHON_BIN}"
      return 0
    fi
    echo "WARN: NOTES_SNAPSHOT_PYTHON_BIN not found or not executable: ${NOTES_SNAPSHOT_PYTHON_BIN}" >&2
  fi

  if [[ -n "${PYTHON_BIN:-}" ]]; then
    if command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
      command -v "${PYTHON_BIN}"
      return 0
    fi
    echo "WARN: PYTHON_BIN not found or not executable: ${PYTHON_BIN}" >&2
  fi

  local repo_root_local="${REPO_ROOT:-}"
  if [[ -z "$repo_root_local" ]]; then
    local source_path="${functions_source[state_find_python]:-}"
    if [[ -n "$source_path" ]]; then
      local source_dir="${source_path:A:h}"
      repo_root_local="${source_dir:h:h}"
    fi
  fi
  if [[ -n "$repo_root_local" ]]; then
    local repo_python="${repo_root_local}/.runtime-cache/dev/venv/bin/python"
    if [[ -x "$repo_python" ]]; then
      printf '%s\n' "$repo_python"
      return 0
    fi
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi
  return 1
}

state_load_state_json() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    return 1
  fi

  local py
  py="$(state_find_python)" || return 1

  local tmp
  tmp="$(state_mktemp)" || return 1
  if ! "$py" - "$path" > "$tmp" <<'PY'
import json
import shlex
import sys

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    sys.exit(1)

def emit(key, value):
    if value is None:
        return
    if isinstance(value, bool):
        value = str(value).lower()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        print(f"{key}={value}")
        return
    print(f"{key}={shlex.quote(str(value))}")

emit("status", data.get("status"))
emit("exit_code", data.get("exit_code"))

last_run_iso = data.get("last_run_iso") or data.get("start_iso") or data.get("end_iso")
last_run_epoch = data.get("last_run_epoch")
if last_run_epoch is None:
    last_run_epoch = data.get("start_epoch")
    if last_run_epoch is None:
        last_run_epoch = data.get("end_epoch")

emit("last_run_iso", last_run_iso)
emit("last_run_epoch", last_run_epoch)
emit("last_success_iso", data.get("last_success_iso"))
emit("last_success_epoch", data.get("last_success_epoch"))
emit("schema_version", data.get("schema_version"))
emit("failure_reason", data.get("failure_reason"))
emit("trigger_source", data.get("trigger_source"))
emit("run_id", data.get("run_id"))
emit("checksum", data.get("checksum"))

missing = [key for key in ("status", "exit_code", "end_iso") if key not in data]
if missing:
    emit("state_json_warning", f"missing_fields:{','.join(missing)}")
PY
  then
    state_rm "$tmp"
    return 1
  fi

  if [[ -s "$tmp" ]]; then
    state_load_kv_file "$tmp"
  fi
  state_rm "$tmp"
}

state_load_state_prefer_json() {
  local state_file="$1"
  local last_run_file="$2"
  local last_success_file="$3"
  local state_json_file="$4"

  state_load_kv_file "$state_file"
  state_load_kv_file "$last_run_file"
  state_load_kv_file "$last_success_file"

  local prefer="${NOTES_SNAPSHOT_PREFER_STATE_JSON:-1}"
  if [[ "$prefer" -eq 0 ]]; then
    return 0
  fi

  local env_status="${STATE_STATUS:-}"
  local env_pid="${pid:-}"
  local env_last_run_epoch="${last_run_epoch:-}"
  local env_last_run_iso="${last_run_iso:-}"

  if ! state_load_state_json "$state_json_file"; then
    return 0
  fi

  if [[ "$env_status" == "running" && -n "${env_pid:-}" ]]; then
    if ps -p "$env_pid" >/dev/null 2>&1; then
      STATE_STATUS="$env_status"
      pid="$env_pid"
      if [[ -n "$env_last_run_epoch" ]]; then
        last_run_epoch="$env_last_run_epoch"
      fi
      if [[ -n "$env_last_run_iso" ]]; then
        last_run_iso="$env_last_run_iso"
      fi
    fi
  fi
}

state_write_metrics_jsonl() {
  local line="$1"
  if [[ -z "$line" ]]; then
    return 0
  fi
  printf '%s\n' "$line" >> "$METRICS_JSONL_FILE"
}

state_write_state_json() {
  local path="$1"
  local run_status="$2"
  local exit_code="$3"
  local duration_sec="$4"
  local start_epoch="$5"
  local start_iso="$6"
  local end_epoch="$7"
  local end_iso="$8"
  local root_dir="$9"
  local exporter_script="${10}"
  local pid="${11}"
  local last_success_iso="${12}"
  local phases_json="${13:-}"
  local pipeline_exit_reason="${14:-}"
  local last_success_epoch="${15:-}"
  local failure_reason="${16:-}"
  local run_id="${17:-}"
  local trigger_source="${18:-}"
  local extra_lines=""

  if [[ -n "$last_success_epoch" ]]; then
    extra_lines+=$',\n  \"last_success_epoch\": '"$last_success_epoch"
  fi
  if [[ -n "$phases_json" ]]; then
    extra_lines+=$',\n  \"phases\": '"$phases_json"
  fi
  if [[ -n "$pipeline_exit_reason" ]]; then
    extra_lines+=$',\n  \"pipeline_exit_reason\": \"'"$(state_json_escape "$pipeline_exit_reason")"'"'
  fi
  if [[ -n "$failure_reason" ]]; then
    extra_lines+=$',\n  \"failure_reason\": \"'"$(state_json_escape "$failure_reason")"'"'
  fi
  if [[ -n "$run_id" ]]; then
    extra_lines+=$',\n  \"run_id\": \"'"$(state_json_escape "$run_id")"'"'
  fi
  if [[ -n "$trigger_source" ]]; then
    extra_lines+=$',\n  \"trigger_source\": \"'"$(state_json_escape "$trigger_source")"'"'
  fi

  local tmp="${path}.tmp.$$"
  /bin/cat <<JSON > "$tmp"
{
  "status": "$(state_json_escape "$run_status")",
  "exit_code": $exit_code,
  "schema_version": $STATE_SCHEMA_VERSION,
  "duration_sec": $duration_sec,
  "start_epoch": $start_epoch,
  "start_iso": "$(state_json_escape "$start_iso")",
  "end_epoch": $end_epoch,
  "end_iso": "$(state_json_escape "$end_iso")",
  "pid": $pid,
  "root_dir": "$(state_json_escape "$root_dir")",
  "exporter_script": "$(state_json_escape "$exporter_script")",
  "last_success_iso": "$(state_json_escape "$last_success_iso")"${extra_lines}
}
JSON
  local py
  py="$(state_find_python)" || py=""
  if [[ -n "$py" ]]; then
    if "$py" - "$tmp" <<'PY'
import hashlib
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
data.pop("checksum", None)
canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
checksum = hashlib.sha256(canonical).hexdigest()
data["checksum"] = checksum
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=True, indent=2)
PY
    then
      /bin/mv -f -- "$tmp" "$path"
    else
      /bin/mv -f -- "$tmp" "$path"
    fi
  else
    /bin/mv -f -- "$tmp" "$path"
  fi
}

state_write_summary() {
  local path="$1"
  local run_status="$2"
  local exit_code="$3"
  local duration_sec="$4"
  local end_iso="$5"
  local last_success_iso="$6"
  local phases_summary="${7:-}"
  local phases_line=""
  if [[ -n "$phases_summary" ]]; then
    phases_line=" phases=${phases_summary}"
  fi
  printf 'status=%s exit_code=%s duration_sec=%s end_iso=%s last_success_iso=%s%s\n' \
    "$run_status" "$exit_code" "$duration_sec" "$end_iso" "$last_success_iso" "$phases_line" > "$path"
}

state_write_state_bundle() {
  local run_status="$1"
  local exit_code="$2"
  local duration_sec="$3"
  local start_epoch="$4"
  local start_iso="$5"
  local end_epoch="$6"
  local end_iso="$7"
  local root_dir="$8"
  local exporter_script="$9"
  local pid="${10}"
  local last_success_iso="${11}"
  local phases_json="${12:-}"
  local phases_summary="${13:-}"
  local pipeline_exit_reason="${14:-}"
  local last_success_epoch="${15:-}"
  local failure_reason="${16:-}"
  local run_id="${17:-}"
  local trigger_source="${18:-}"

  if [[ "$NOTES_SNAPSHOT_WRITE_STATE_JSON" -eq 1 ]]; then
    state_write_state_json "$STATE_JSON_FILE" "$run_status" "$exit_code" "$duration_sec" \
      "$start_epoch" "$start_iso" "$end_epoch" "$end_iso" \
      "$root_dir" "$exporter_script" "$pid" "$last_success_iso" \
      "$phases_json" "$pipeline_exit_reason" "$last_success_epoch" "$failure_reason" "$run_id" "$trigger_source"
  fi

  state_write_env_file "$STATE_FILE" \
    "$(state_kv_line status "$run_status")" \
    "$(state_kv_line start_epoch "$start_epoch")" \
    "$(state_kv_line start_iso "$start_iso")" \
    "$(state_kv_line end_epoch "$end_epoch")" \
    "$(state_kv_line end_iso "$end_iso")" \
    "$(state_kv_line duration_sec "$duration_sec")" \
    "$(state_kv_line exit_code "$exit_code")" \
    "$(state_kv_line pid "$pid")" \
    "$(state_kv_line root_dir "$root_dir")" \
    "$(state_kv_line exporter_script "$exporter_script")" \
    "$(state_kv_line run_id "$run_id")" \
    "$(state_kv_line trigger_source "$trigger_source")"

  if [[ "$NOTES_SNAPSHOT_WRITE_SUMMARY" -eq 1 ]]; then
    state_write_summary "$SUMMARY_FILE" "$run_status" "$exit_code" "$duration_sec" "$end_iso" "$last_success_iso" "$phases_summary"
  fi
}
