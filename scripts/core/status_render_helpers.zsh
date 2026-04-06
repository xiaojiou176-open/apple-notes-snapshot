#!/bin/zsh

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
