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
OUTPUT_JSON=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json)
      OUTPUT_JSON=1
      shift
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
LAUNCHD_LABEL="${NOTES_SNAPSHOT_LAUNCHD_LABEL:-local.apple-notes-snapshot}"
PLIST_PATH="${REPO_ROOT}/generated/launchd/${LAUNCHD_LABEL}.plist"

state_set_paths "$NOTES_SNAPSHOT_STATE_DIR"
EXPORTER_SCRIPT="${NOTES_SNAPSHOT_DIR}/exportnotes.zsh"

WARNINGS=()
OPERATOR_SUMMARY=""
CONFIG_LAYER_STATUS="configured"
CONFIG_LAYER_SUMMARY="Config surface resolved for root, state, logs, and interval."
LAUNCHD_LAYER_STATUS="unknown"
LAUNCHD_LAYER_SUMMARY="Launchd state has not been checked yet."
LEDGER_LAYER_STATUS="unknown"
LEDGER_LAYER_SUMMARY="The local state ledger has not been interpreted yet."

emit_warn() {
  local msg="$1"
  if [[ "$OUTPUT_JSON" -eq 1 ]]; then
    WARNINGS+=("$msg")
  else
    echo "WARN: $msg"
  fi
}

emit_info() {
  local msg="$1"
  if [[ "$OUTPUT_JSON" -eq 0 ]]; then
    echo "INFO: $msg"
  fi
}

MISSING_VENDOR=0
MISSING_EXPORTER=0
MISSING_ROOT=0
MISSING_LOG=0
MISSING_STATE=0
MISSING_PLIST=0
LAUNCHD_LOADED=1

# ------------------------------
# Basic checks
# ------------------------------
emit_info "Repo root: $REPO_ROOT"
emit_info "Exporter dir: $NOTES_SNAPSHOT_DIR"
emit_info "Root dir: $NOTES_SNAPSHOT_ROOT_DIR"
emit_info "Log dir: $NOTES_SNAPSHOT_LOG_DIR"
emit_info "State dir: $NOTES_SNAPSHOT_STATE_DIR"
emit_info "Lock dir: $NOTES_SNAPSHOT_LOCK_DIR"
emit_info "Interval minutes: $NOTES_SNAPSHOT_INTERVAL_MINUTES"
if [[ -n "$NOTES_SNAPSHOT_VENDOR_REF" ]]; then
  emit_info "Vendor ref: $NOTES_SNAPSHOT_VENDOR_REF"
fi

if [[ ! -d "$NOTES_SNAPSHOT_DIR" ]]; then
  emit_warn "vendor/notes-exporter missing"
  MISSING_VENDOR=1
fi

if [[ ! -f "${NOTES_SNAPSHOT_DIR}/VENDOR_INFO" ]]; then
  emit_warn "VENDOR_INFO missing; run ./notesctl update-vendor (first run generates VENDOR_INFO)"
fi

if [[ ! -x "$EXPORTER_SCRIPT" ]]; then
  emit_warn "exportnotes.zsh not executable: $EXPORTER_SCRIPT"
  MISSING_EXPORTER=1
fi

if [[ ! -d "$NOTES_SNAPSHOT_ROOT_DIR" ]]; then
  emit_warn "root dir missing: $NOTES_SNAPSHOT_ROOT_DIR"
  MISSING_ROOT=1
fi

if [[ ! -d "$NOTES_SNAPSHOT_LOG_DIR" ]]; then
  MISSING_LOG=1
fi

if [[ ! -d "$NOTES_SNAPSHOT_STATE_DIR" ]]; then
  MISSING_STATE=1
fi

if [[ ! -f "$PLIST_PATH" ]]; then
  emit_warn "launchd plist missing in repo: $PLIST_PATH"
  MISSING_PLIST=1
fi

# ------------------------------
# Interval sanity
# ------------------------------
if [[ ! "$NOTES_SNAPSHOT_INTERVAL_MINUTES" =~ ^[0-9]+$ ]]; then
  emit_warn "NOTES_SNAPSHOT_INTERVAL_MINUTES not numeric"
else
  if [[ "$NOTES_SNAPSHOT_INTERVAL_MINUTES" -ne 30 ]]; then
    emit_warn "interval is not 30 minutes (current=${NOTES_SNAPSHOT_INTERVAL_MINUTES})"
  fi
fi

if [[ -n "$NOTES_SNAPSHOT_TIMEOUT_SEC" ]]; then
  if [[ ! "$NOTES_SNAPSHOT_TIMEOUT_SEC" =~ ^[0-9]+$ ]]; then
    emit_warn "NOTES_SNAPSHOT_TIMEOUT_SEC not numeric"
  else
    INTERVAL_SEC=$(( NOTES_SNAPSHOT_INTERVAL_MINUTES * 60 ))
    if [[ "$NOTES_SNAPSHOT_TIMEOUT_SEC" -ge "$INTERVAL_SEC" ]]; then
      emit_warn "timeout >= interval; consider reducing timeout to avoid overlap"
    fi
  fi
fi

# ------------------------------
# Web UI sanity
# ------------------------------
if [[ "${NOTES_SNAPSHOT_WEB_ENABLE}" == "1" ]]; then
  if [[ "${NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN}" == "1" && -z "${NOTES_SNAPSHOT_WEB_TOKEN}" ]]; then
    emit_warn "web token required but NOTES_SNAPSHOT_WEB_TOKEN is empty"
  fi
  if [[ "${NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN_FOR_STATIC}" == "1" && -z "${NOTES_SNAPSHOT_WEB_TOKEN}" ]]; then
    emit_warn "web static token required but NOTES_SNAPSHOT_WEB_TOKEN is empty"
  fi

  if [[ "${NOTES_SNAPSHOT_WEB_ALLOW_REMOTE}" == "1" ]]; then
    if [[ "${NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN}" != "1" ]]; then
      emit_warn "web allow remote without token requirement"
    fi
    if [[ -z "${NOTES_SNAPSHOT_WEB_ALLOW_IPS}" ]]; then
      emit_warn "web allow remote with empty allowlist"
    fi
  fi

  if [[ -n "${NOTES_SNAPSHOT_WEB_MAX_TAIL_LINES}" ]]; then
    if [[ ! "${NOTES_SNAPSHOT_WEB_MAX_TAIL_LINES}" =~ ^[0-9]+$ ]]; then
      emit_warn "NOTES_SNAPSHOT_WEB_MAX_TAIL_LINES not numeric"
    else
      if [[ "${NOTES_SNAPSHOT_WEB_MAX_TAIL_LINES}" -lt 1 ]]; then
        emit_warn "NOTES_SNAPSHOT_WEB_MAX_TAIL_LINES must be >= 1"
      elif [[ "${NOTES_SNAPSHOT_WEB_MAX_TAIL_LINES}" -gt 10000 ]]; then
        emit_warn "NOTES_SNAPSHOT_WEB_MAX_TAIL_LINES unusually large (>10000)"
      fi
    fi
  fi

  if [[ -n "${NOTES_SNAPSHOT_WEB_RATE_LIMIT_WINDOW_SEC}" ]]; then
    if [[ ! "${NOTES_SNAPSHOT_WEB_RATE_LIMIT_WINDOW_SEC}" =~ ^-?[0-9]+$ ]]; then
      emit_warn "NOTES_SNAPSHOT_WEB_RATE_LIMIT_WINDOW_SEC not numeric"
    elif [[ "${NOTES_SNAPSHOT_WEB_RATE_LIMIT_WINDOW_SEC}" -lt 0 ]]; then
      emit_warn "NOTES_SNAPSHOT_WEB_RATE_LIMIT_WINDOW_SEC must be >= 0"
    fi
  fi
  if [[ -n "${NOTES_SNAPSHOT_WEB_RATE_LIMIT_MAX}" ]]; then
    if [[ ! "${NOTES_SNAPSHOT_WEB_RATE_LIMIT_MAX}" =~ ^-?[0-9]+$ ]]; then
      emit_warn "NOTES_SNAPSHOT_WEB_RATE_LIMIT_MAX not numeric"
    elif [[ "${NOTES_SNAPSHOT_WEB_RATE_LIMIT_MAX}" -lt 0 ]]; then
      emit_warn "NOTES_SNAPSHOT_WEB_RATE_LIMIT_MAX must be >= 0"
    fi
  fi
fi

if [[ "${NOTES_SNAPSHOT_WEB_ENABLE}" == "1" && -n "${NOTES_SNAPSHOT_WEB_ACTION_COOLDOWNS}" ]]; then
  local raw_cooldowns="${NOTES_SNAPSHOT_WEB_ACTION_COOLDOWNS}"
  if [[ "${raw_cooldowns:l}" == "off" || "${raw_cooldowns:l}" == "none" || "${raw_cooldowns:l}" == "0" ]]; then
    :
  else
    local -a cooldown_items bad_cooldowns
    IFS=',' read -r -A cooldown_items <<< "${raw_cooldowns}"
    for item in "${cooldown_items[@]}"; do
      item="$(printf '%s' "$item" | tr -d '[:space:]')"
      if [[ -z "$item" ]]; then
        continue
      fi
      if [[ "$item" != *=* ]]; then
        bad_cooldowns+=("$item")
        continue
      fi
      local action="${item%%=*}"
      local value="${item#*=}"
      if [[ ! "$value" =~ ^[0-9]+$ ]]; then
        bad_cooldowns+=("$item")
        continue
      fi
      case "$action" in
        run|setup|verify|fix|self-heal|install|ensure|rotate-logs|update-vendor|permissions|logs)
          ;;
        *)
          bad_cooldowns+=("$item")
          ;;
      esac
    done
    if [[ "${#bad_cooldowns[@]}" -gt 0 ]]; then
      emit_warn "web action cooldowns invalid: ${bad_cooldowns[*]}"
    fi
  fi
fi

if [[ -n "${NOTES_SNAPSHOT_WEB_TOKEN_SCOPES}" && "${NOTES_SNAPSHOT_WEB_TOKEN_SCOPES}" != "all" ]]; then
  local -a scopes unknown
  IFS=',' read -r -A scopes <<< "${NOTES_SNAPSHOT_WEB_TOKEN_SCOPES}"
  for scope in "${scopes[@]}"; do
    scope="$(printf '%s' "$scope" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')"
    if [[ -z "$scope" ]]; then
      continue
    fi
    case "$scope" in
      read|run|install|vendor|logs|system)
        ;;
      *)
        unknown+=("$scope")
        ;;
    esac
  done
  if [[ "${#unknown[@]}" -gt 0 ]]; then
    emit_warn "web token scopes invalid: ${unknown[*]}"
  fi
fi

if [[ -n "${NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW}" && "${NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW}" != "all" ]]; then
  local -a actions bad_actions
  IFS=',' read -r -A actions <<< "${NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW}"
  for action in "${actions[@]}"; do
    action="$(printf '%s' "$action" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')"
    if [[ -z "$action" ]]; then
      continue
    fi
    case "$action" in
      run|setup|verify|fix|self-heal|install|ensure|rotate-logs|update-vendor|permissions|logs)
        ;;
      *)
        bad_actions+=("$action")
        ;;
    esac
  done
  if [[ "${#bad_actions[@]}" -gt 0 ]]; then
    emit_warn "web actions allowlist invalid: ${bad_actions[*]}"
  fi
fi

if [[ -n "${NOTES_SNAPSHOT_WEB_TOKEN_SCOPES}" && "${NOTES_SNAPSHOT_WEB_TOKEN_SCOPES}" != "all" ]] \
  && [[ -n "${NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW}" && "${NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW}" != "all" ]]; then
  local -a scope_list action_list mismatched
  local scopes_csv=","
  IFS=',' read -r -A scope_list <<< "${NOTES_SNAPSHOT_WEB_TOKEN_SCOPES}"
  for scope in "${scope_list[@]}"; do
    scope="$(printf '%s' "$scope" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')"
    if [[ -n "$scope" ]]; then
      scopes_csv+="${scope},"
    fi
  done
  IFS=',' read -r -A action_list <<< "${NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW}"
  for action in "${action_list[@]}"; do
    action="$(printf '%s' "$action" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')"
    if [[ -z "$action" ]]; then
      continue
    fi
    local required=""
    case "$action" in
      run|setup|verify|fix|self-heal)
        required="run"
        ;;
      install|ensure)
        required="install"
        ;;
      rotate-logs|logs)
        required="logs"
        ;;
      update-vendor)
        required="vendor"
        ;;
      permissions)
        required="system"
        ;;
    esac
    if [[ -n "$required" && "$scopes_csv" != *",$required,"* ]]; then
      mismatched+=("${action}:${required}")
    fi
  done
  if [[ "${#mismatched[@]}" -gt 0 ]]; then
    emit_warn "web actions not covered by token scopes: ${mismatched[*]}"
  fi
fi

# ------------------------------
# Last success staleness
# ------------------------------
state_load_state_prefer_json "$STATE_FILE" "$LAST_RUN_FILE" "$LAST_SUCCESS_FILE" "$STATE_JSON_FILE"
if [[ -n "${state_json_warning:-}" ]]; then
  emit_warn "state.json warning: ${state_json_warning}"
fi
if [[ -n "${STATE_STATUS:-}" && -n "${exit_code:-}" ]]; then
  if [[ "${STATE_STATUS}" == "success" && "${exit_code}" != "0" ]]; then
    emit_warn "status/exit mismatch: status=success exit_code=${exit_code}"
  elif [[ "${STATE_STATUS}" == "failed" && "${exit_code}" == "0" ]]; then
    emit_warn "status/exit mismatch: status=failed exit_code=0"
  fi
fi
if [[ -n "${last_success_epoch:-}" ]]; then
  NOW_EPOCH="$(date +%s)"
  AGE_SEC=$(( NOW_EPOCH - last_success_epoch ))
  if [[ "$AGE_SEC" -gt "$NOTES_SNAPSHOT_STALE_THRESHOLD_SEC" ]]; then
    emit_warn "last success is stale (${AGE_SEC}s > ${NOTES_SNAPSHOT_STALE_THRESHOLD_SEC}s)"
    last_success_stale=1
    LEDGER_LAYER_STATUS="stale"
    LEDGER_LAYER_SUMMARY="A successful snapshot exists, but it is older than the freshness threshold."
  else
    last_success_stale=0
    LEDGER_LAYER_STATUS="fresh"
    LEDGER_LAYER_SUMMARY="A successful snapshot is recorded in the local state ledger."
  fi
else
  last_success_stale=0
  emit_warn "no successful snapshot recorded yet; run ./notesctl run --no-status once to initialize the ledger"
  LEDGER_LAYER_STATUS="needs_first_run"
  LEDGER_LAYER_SUMMARY="No successful snapshot is recorded yet. Run one manual snapshot to initialize the ledger."
fi

# ------------------------------
# Launchd status
# ------------------------------
if command -v launchctl >/dev/null 2>&1; then
  local launchd_summary=""
  launchd_summary="$(launchctl print "gui/$(id -u)/${LAUNCHD_LABEL}" 2>/dev/null | \
    grep -E 'state =|path =|last exit|run interval|run count' || true)"
  if [[ "$OUTPUT_JSON" -eq 0 ]]; then
    echo ""
    echo "Launchd"
  fi
  if [[ -n "$launchd_summary" ]]; then
    LAUNCHD_LAYER_STATUS="loaded"
    LAUNCHD_LAYER_SUMMARY="launchctl reports ${LAUNCHD_LABEL} is loaded."
    if [[ "$OUTPUT_JSON" -eq 0 ]]; then
      printf '%s\n' "$launchd_summary"
    fi
  else
    emit_warn "launchd job not loaded"
    LAUNCHD_LOADED=0
    LAUNCHD_LAYER_STATUS="not_loaded"
    LAUNCHD_LAYER_SUMMARY="launchctl does not currently report ${LAUNCHD_LABEL} as loaded."
  fi
fi

if [[ "$MISSING_LOG" -eq 1 && "$LEDGER_LAYER_STATUS" != "needs_first_run" ]]; then
  emit_warn "log dir missing: $NOTES_SNAPSHOT_LOG_DIR"
fi

if [[ "$MISSING_STATE" -eq 1 && "$LEDGER_LAYER_STATUS" != "needs_first_run" ]]; then
  emit_warn "state dir missing: $NOTES_SNAPSHOT_STATE_DIR"
fi

if [[ "$LEDGER_LAYER_STATUS" == "needs_first_run" ]]; then
  OPERATOR_SUMMARY="This looks like a first-run or cleaned-checkout baseline. Finish one successful manual snapshot before treating it as an active runtime failure."
elif [[ "$LAUNCHD_LAYER_STATUS" == "not_loaded" ]]; then
  OPERATOR_SUMMARY="The scheduler is not currently loaded, so the backup loop is not running on its own."
elif [[ "$LEDGER_LAYER_STATUS" == "stale" ]]; then
  OPERATOR_SUMMARY="A successful snapshot exists, but it is outside the freshness target."
elif [[ "$LEDGER_LAYER_STATUS" == "failed" ]]; then
  OPERATOR_SUMMARY="The local state ledger points to a failed run and still needs a successful recovery baseline."
else
  OPERATOR_SUMMARY="The deterministic control-room surfaces are present; use warnings below to inspect any remaining gaps."
fi

if [[ "$OUTPUT_JSON" -eq 0 ]]; then
  echo ""
  echo "State Layers"
  echo "  config: ${CONFIG_LAYER_STATUS} - ${CONFIG_LAYER_SUMMARY}"
  echo "  launchd: ${LAUNCHD_LAYER_STATUS} - ${LAUNCHD_LAYER_SUMMARY}"
  echo "  ledger: ${LEDGER_LAYER_STATUS} - ${LEDGER_LAYER_SUMMARY}"
  echo ""
  echo "Operator Summary"
  echo "  ${OPERATOR_SUMMARY}"
fi

# ------------------------------
# State snapshot
# ------------------------------
if [[ -f "$STATE_FILE" ]]; then
  if [[ "$OUTPUT_JSON" -eq 0 ]]; then
    echo ""
    echo "State"
    cat "$STATE_FILE"
  fi
fi

# ------------------------------
# Suggested fixes
# ------------------------------
if [[ "$OUTPUT_JSON" -eq 0 ]]; then
  echo ""
  echo "Suggested Fixes"
  if [[ "$MISSING_VENDOR" -eq 1 || "$MISSING_EXPORTER" -eq 1 ]]; then
    echo " - run: ./notesctl update-vendor"
  fi
  if [[ "$MISSING_ROOT" -eq 1 || "$MISSING_LOG" -eq 1 || "$MISSING_STATE" -eq 1 ]]; then
    echo " - run: ./notesctl run"
  fi
  if [[ "$MISSING_PLIST" -eq 1 || "$LAUNCHD_LOADED" -eq 0 ]]; then
    echo " - run: ./notesctl install --minutes 30 --load"
  fi

  # ------------------------------
  # Permissions checklist (manual)
  # ------------------------------
  echo ""
  echo "Permissions Checklist (manual)"
  echo "1) System Settings -> Privacy & Security -> Full Disk Access -> allow Terminal/iTerm"
  echo "2) System Settings -> Privacy & Security -> Automation -> allow Terminal to control Notes"
  echo "3) If prompts appear on first run, always click Allow"
  echo "Hint: run ./notesctl permissions"
fi

# ------------------------------
# Dependencies preflight
# ------------------------------
PYTHON_BIN=""
if PYTHON_BIN="$(state_find_python 2>/dev/null)"; then
  :
else
  PYTHON_BIN=""
  emit_warn "python3/python not found; required for dashboard and JSON helpers"
fi

HAS_OSASCRIPT=0
if command -v osascript >/dev/null 2>&1; then
  HAS_OSASCRIPT=1
else
  emit_warn "osascript not found; required for Apple Notes export"
fi

HAS_LAUNCHCTL=0
if command -v launchctl >/dev/null 2>&1; then
  HAS_LAUNCHCTL=1
else
  emit_warn "launchctl not found; launchd checks unavailable"
fi

HAS_PLUTIL=0
if command -v plutil >/dev/null 2>&1; then
  HAS_PLUTIL=1
else
  emit_warn "plutil not found; plist inspection may be limited"
fi

TIMEOUT_BIN=""
if command -v gtimeout >/dev/null 2>&1; then
  TIMEOUT_BIN="gtimeout"
elif command -v timeout >/dev/null 2>&1; then
  TIMEOUT_BIN="timeout"
else
  TIMEOUT_BIN=""
fi

if [[ "$OUTPUT_JSON" -eq 0 ]]; then
  echo ""
  echo "Dependencies"
  echo "python_bin=${PYTHON_BIN:-"(missing)"}"
  echo "osascript=$([[ "$HAS_OSASCRIPT" -eq 1 ]] && echo "ok" || echo "missing")"
  echo "launchctl=$([[ "$HAS_LAUNCHCTL" -eq 1 ]] && echo "ok" || echo "missing")"
  echo "plutil=$([[ "$HAS_PLUTIL" -eq 1 ]] && echo "ok" || echo "missing")"
  echo "timeout_bin=${TIMEOUT_BIN:-"(missing)"}"
fi

if [[ "$OUTPUT_JSON" -eq 1 ]]; then
  json_escape() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    printf '%s' "$value"
  }
  json_bool() {
    if [[ "$1" -eq 1 ]]; then
      echo "true"
    else
      echo "false"
    fi
  }
  warnings_json=""
  if [[ "${#WARNINGS[@]}" -gt 0 ]]; then
    local first=1
    local w
    for w in "${WARNINGS[@]}"; do
      if [[ "$first" -eq 1 ]]; then
        warnings_json="\"$(json_escape "$w")\""
        first=0
      else
        warnings_json="${warnings_json},\"$(json_escape "$w")\""
      fi
    done
  fi

  local stale_bool="false"
  local last_success_age_sec=""
  if [[ -n "${last_success_epoch:-}" ]]; then
    last_success_age_sec=$(( $(date +%s) - last_success_epoch ))
    if [[ "$last_success_age_sec" -gt "$NOTES_SNAPSHOT_STALE_THRESHOLD_SEC" ]]; then
      stale_bool="true"
    fi
  fi

  cat <<JSON
{
  "repo_root": "$(json_escape "$REPO_ROOT")",
  "vendor_dir": "$(json_escape "$NOTES_SNAPSHOT_DIR")",
  "vendor_info_exists": $(json_bool $([[ -f "${NOTES_SNAPSHOT_DIR}/VENDOR_INFO" ]] && echo 1 || echo 0)),
  "exporter_script": "$(json_escape "$EXPORTER_SCRIPT")",
  "exporter_executable": $(json_bool $([[ -x "$EXPORTER_SCRIPT" ]] && echo 1 || echo 0)),
  "root_dir": "$(json_escape "$NOTES_SNAPSHOT_ROOT_DIR")",
  "log_dir": "$(json_escape "$NOTES_SNAPSHOT_LOG_DIR")",
  "state_dir": "$(json_escape "$NOTES_SNAPSHOT_STATE_DIR")",
  "lock_dir": "$(json_escape "$NOTES_SNAPSHOT_LOCK_DIR")",
  "interval_minutes": $NOTES_SNAPSHOT_INTERVAL_MINUTES,
  "timeout_sec": "$(json_escape "${NOTES_SNAPSHOT_TIMEOUT_SEC:-}")",
  "last_success_epoch": "$(json_escape "${last_success_epoch:-}")",
  "last_success_age_sec": "$(json_escape "${last_success_age_sec:-}")",
  "last_success_stale": $stale_bool,
  "operator_summary": "$(json_escape "${OPERATOR_SUMMARY}")",
  "launchd_loaded": $(json_bool $LAUNCHD_LOADED),
  "plist_exists": $(json_bool $([[ -f "$PLIST_PATH" ]] && echo 1 || echo 0)),
  "state_layers": {
    "config": {
      "status": "$(json_escape "$CONFIG_LAYER_STATUS")",
      "summary": "$(json_escape "$CONFIG_LAYER_SUMMARY")"
    },
    "launchd": {
      "status": "$(json_escape "$LAUNCHD_LAYER_STATUS")",
      "summary": "$(json_escape "$LAUNCHD_LAYER_SUMMARY")"
    },
    "ledger": {
      "status": "$(json_escape "$LEDGER_LAYER_STATUS")",
      "summary": "$(json_escape "$LEDGER_LAYER_SUMMARY")"
    }
  },
  "dependencies": {
    "python_bin": "$(json_escape "${PYTHON_BIN:-}")",
    "osascript": $(json_bool $HAS_OSASCRIPT),
    "launchctl": $(json_bool $HAS_LAUNCHCTL),
    "plutil": $(json_bool $HAS_PLUTIL),
    "timeout_bin": "$(json_escape "${TIMEOUT_BIN:-}")"
  },
  "warnings": [${warnings_json}]
}
JSON
fi
