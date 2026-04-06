#!/bin/zsh
set -euo pipefail

# This helper only supports optional external desktop launcher artifacts.
# It is not a repo-owned desktop app installer and the repo does not require
# a committed .app bundle to function.

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

load_env_with_defaults

validate_abs_path "REPO_ROOT" "$REPO_ROOT"
validate_abs_path "NOTES_SNAPSHOT_LOG_DIR" "$NOTES_SNAPSHOT_LOG_DIR"
validate_abs_path "NOTES_SNAPSHOT_STATE_DIR" "$NOTES_SNAPSHOT_STATE_DIR"

APP_PATH="${ZERO_CLI_APP_PATH:-}"
ADD_LOGIN_ITEM="${ZERO_CLI_ADD_LOGIN_ITEM:-0}"

notify() {
  /usr/bin/osascript -e "display notification \"$1\" with title \"Apple Notes Snapshot\"" >/dev/null 2>&1 || true
}

touch "$NOTES_SNAPSHOT_LOG_DIR/zero_cli_install.log" || true

notify "Installing launchd services..."
"$REPO_ROOT/notesctl" install --minutes "$NOTES_SNAPSHOT_INTERVAL_MINUTES" --load --web >> "$NOTES_SNAPSHOT_LOG_DIR/zero_cli_install.log" 2>&1

if [[ -n "$APP_PATH" && "$ADD_LOGIN_ITEM" -eq 1 ]]; then
  /usr/bin/osascript <<EOF_OSA >/dev/null 2>&1
    tell application "System Events"
      if not (exists login item "Notes Snapshot Console") then
        make login item at end with properties {path:"$APP_PATH", hidden:true}
      end if
    end tell
EOF_OSA
fi

notify "Opening Web UI..."
open "http://${NOTES_SNAPSHOT_WEB_HOST}:${NOTES_SNAPSHOT_WEB_PORT}" >/dev/null 2>&1 || true

exit 0
