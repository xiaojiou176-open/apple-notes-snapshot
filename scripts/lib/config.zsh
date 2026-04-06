#!/bin/zsh

# ------------------------------
# Config helpers (sourced)
# Requires: ENV_FILE, REPO_ROOT, load_env (lib/common.zsh)
# ------------------------------
load_env_with_defaults() {
  load_env

  local xdg_cache_home_default="${XDG_CACHE_HOME:-$HOME/.cache}"
  local repo_runtime_root_default="${REPO_ROOT}/.runtime-cache"
  local repo_cache_root_default="${repo_runtime_root_default}/cache/apple-notes-snapshot"
  local external_cache_root_default="${xdg_cache_home_default}/apple-notes-snapshot"
  local repo_python_default=""
  local fallback_python_default=""
  if [[ -x "${repo_runtime_root_default}/dev/venv/bin/python" ]]; then
    repo_python_default="${repo_runtime_root_default}/dev/venv/bin/python"
  fi
  if [[ -z "$repo_python_default" ]]; then
    if command -v python3 >/dev/null 2>&1; then
      fallback_python_default="$(command -v python3)"
    elif command -v python >/dev/null 2>&1; then
      fallback_python_default="$(command -v python)"
    fi
  fi

  : "${NOTES_SNAPSHOT_ROOT_DIR:="$HOME/iCloudDrive/NotesSnapshots"}"
  : "${NOTES_SNAPSHOT_DIR:="${REPO_ROOT}/vendor/notes-exporter"}"
  : "${NOTES_SNAPSHOT_RUNTIME_ROOT:="${repo_runtime_root_default}"}"
  : "${NOTES_SNAPSHOT_CACHE_DIR:="${repo_cache_root_default}"}"
  : "${NOTES_SNAPSHOT_LOG_DIR:="${NOTES_SNAPSHOT_RUNTIME_ROOT}/logs/apple-notes-snapshot"}"
  : "${NOTES_SNAPSHOT_LOCK_DIR:="${NOTES_SNAPSHOT_CACHE_DIR}/lock/mkdir"}"
  : "${NOTES_SNAPSHOT_LOCK_FILE:="${NOTES_SNAPSHOT_CACHE_DIR}/lock/flock.lock"}"
  : "${NOTES_SNAPSHOT_STATE_DIR:="${NOTES_SNAPSHOT_CACHE_DIR}/state"}"
  : "${NOTES_SNAPSHOT_TEMP_DIR:="${NOTES_SNAPSHOT_RUNTIME_ROOT}/temp"}"
  : "${NOTES_SNAPSHOT_PYTHONPYCACHEPREFIX:="${NOTES_SNAPSHOT_RUNTIME_ROOT}/pycache"}"
  : "${NOTES_SNAPSHOT_PYTEST_CACHE_DIR:="${NOTES_SNAPSHOT_RUNTIME_ROOT}/pytest"}"
  : "${NOTES_SNAPSHOT_COVERAGE_FILE:="${NOTES_SNAPSHOT_RUNTIME_ROOT}/coverage/.coverage"}"
  : "${NOTES_SNAPSHOT_EXTERNAL_CACHE_ROOT:="${external_cache_root_default}"}"
  : "${NOTES_SNAPSHOT_VENDOR_RUNTIME_ROOT:="${NOTES_SNAPSHOT_EXTERNAL_CACHE_ROOT}/vendor-runtime/current"}"
  : "${NOTES_SNAPSHOT_EXTERNAL_CACHE_TTL_HOURS:="72"}"
  : "${NOTES_SNAPSHOT_EXTERNAL_CACHE_MAX_BYTES:="2147483648"}"
  : "${NOTES_SNAPSHOT_BROWSER_CLONE_TTL_HOURS:="24"}"
  : "${NOTES_SNAPSHOT_RUNTIME_AUTO_CLEAN:="1"}"
  : "${NOTES_SNAPSHOT_BROWSER_PROVIDER:="chrome"}"
  : "${NOTES_SNAPSHOT_BROWSER_ROOT:="${NOTES_SNAPSHOT_EXTERNAL_CACHE_ROOT}/browser"}"
  : "${NOTES_SNAPSHOT_CHROME_USER_DATA_DIR:="${NOTES_SNAPSHOT_BROWSER_ROOT}/chrome-user-data"}"
  : "${NOTES_SNAPSHOT_CHROME_PROFILE_NAME:="apple-notes-snapshot"}"
  : "${NOTES_SNAPSHOT_CHROME_PROFILE_DIR:="Profile 1"}"
  : "${NOTES_SNAPSHOT_CHROME_CHANNEL:="chrome"}"
  : "${NOTES_SNAPSHOT_CHROME_CDP_HOST:="127.0.0.1"}"
  : "${NOTES_SNAPSHOT_CHROME_CDP_PORT:="9337"}"
  : "${NOTES_SNAPSHOT_BROWSER_TEMP_ROOT:="${NOTES_SNAPSHOT_BROWSER_CACHE_ROOT:-${NOTES_SNAPSHOT_BROWSER_ROOT}/tmp}"}"
  : "${NOTES_SNAPSHOT_BROWSER_CACHE_ROOT:="${NOTES_SNAPSHOT_BROWSER_TEMP_ROOT}"}"

  : "${NOTES_SNAPSHOT_INTERVAL_MINUTES:="30"}"
  : "${NOTES_SNAPSHOT_CALENDAR_MINUTES:=""}"
  : "${NOTES_SNAPSHOT_LAUNCHD_LABEL:="local.apple-notes-snapshot"}"
  : "${NOTES_SNAPSHOT_LAUNCHD_WEB_LABEL:="${NOTES_SNAPSHOT_LAUNCHD_LABEL}.webui"}"
  : "${NOTES_SNAPSHOT_LAUNCHD_WATCH_PATHS:=""}"
  : "${NOTES_SNAPSHOT_LAUNCHD_QUEUE_DIRS:=""}"
  : "${NOTES_SNAPSHOT_LAUNCHD_THROTTLE_SEC:=""}"

  : "${NOTES_SNAPSHOT_STALE_THRESHOLD_SEC:="7200"}"
  : "${NOTES_SNAPSHOT_TIMEOUT_SEC:=""}"
  : "${NOTES_SNAPSHOT_LOG_MAX_BYTES:="5242880"}"
  : "${NOTES_SNAPSHOT_LOG_BACKUPS:="5"}"
  : "${NOTES_SNAPSHOT_LOG_ROTATE_MODE:="copytruncate"}"
  : "${NOTES_SNAPSHOT_LOG_JSONL:="0"}"
  : "${NOTES_SNAPSHOT_LOCK_TTL_SEC:="0"}"
  : "${NOTES_SNAPSHOT_WRITE_STATE_JSON:="1"}"
  : "${NOTES_SNAPSHOT_WRITE_SUMMARY:="1"}"
  : "${NOTES_SNAPSHOT_PREFER_STATE_JSON:="${PREFER_STATE_JSON:-1}"}"
  : "${NOTES_SNAPSHOT_TAIL_LINES:="200"}"
  : "${NOTES_SNAPSHOT_PYTHON_BIN:="${repo_python_default:-$fallback_python_default}"}"
  : "${NOTES_SNAPSHOT_VENDOR_REF:=""}"
  : "${NOTES_SNAPSHOT_VENDOR_URL:="https://github.com/storizzi/notes-exporter.git"}"
  : "${NOTES_SNAPSHOT_VENDOR_PATCH_DIR:="${REPO_ROOT}/vendor_patches"}"
  : "${NOTES_SNAPSHOT_LOG_HEALTH_PATTERN:="(ERROR|Error|FAIL|Failed|Traceback|Exception|command not found: python|export_notes\\.scpt: No such file or directory)"}"
  : "${NOTES_SNAPSHOT_WEB_HOST:="127.0.0.1"}"
  : "${NOTES_SNAPSHOT_WEB_PORT:="8787"}"
  : "${NOTES_SNAPSHOT_WEB_CMD_TIMEOUT_SEC:="10"}"
  : "${NOTES_SNAPSHOT_WEB_ENABLE:="0"}"
  : "${NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN:="1"}"
  : "${NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN_FOR_STATIC:="0"}"
  : "${NOTES_SNAPSHOT_WEB_TOKEN:=""}"
  : "${NOTES_SNAPSHOT_WEB_ALLOW_REMOTE:="0"}"
  : "${NOTES_SNAPSHOT_WEB_READONLY:="0"}"
  : "${NOTES_SNAPSHOT_WEB_MAX_TAIL_LINES:="2000"}"
  : "${NOTES_SNAPSHOT_WEB_ALLOW_IPS:=""}"
  : "${NOTES_SNAPSHOT_WEB_TOKEN_SCOPES:=""}"
  : "${NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW:=""}"
  : "${NOTES_SNAPSHOT_WEB_RATE_LIMIT_WINDOW_SEC:="60"}"
  : "${NOTES_SNAPSHOT_WEB_RATE_LIMIT_MAX:="120"}"
  : "${NOTES_SNAPSHOT_WEB_ACTION_COOLDOWNS:=""}"
  : "${NOTES_SNAPSHOT_TRIGGER_SOURCE:=""}"

  export PYTHONPYCACHEPREFIX="${NOTES_SNAPSHOT_PYTHONPYCACHEPREFIX}"
  export COVERAGE_FILE="${NOTES_SNAPSHOT_COVERAGE_FILE}"

}
