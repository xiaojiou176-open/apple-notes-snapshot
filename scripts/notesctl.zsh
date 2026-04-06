#!/bin/zsh
set -euo pipefail

# ------------------------------
# Paths
# ------------------------------
SCRIPT_DIR="${0:A:h}"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ENV_FILE="${REPO_ROOT}/config/notes_snapshot.env"

WRAPPER_SCRIPT="${REPO_ROOT}/scripts/core/notes_snapshot_wrapper.zsh"
STATUS_SCRIPT="${REPO_ROOT}/scripts/core/status_notes_snapshot.zsh"
VERIFY_SCRIPT="${REPO_ROOT}/scripts/core/verify_ok.zsh"
DOCTOR_SCRIPT="${REPO_ROOT}/scripts/core/doctor_notes_snapshot.zsh"
LOGS_SCRIPT="${REPO_ROOT}/scripts/ops/logs_follow.zsh"
ROTATE_SCRIPT="${REPO_ROOT}/scripts/ops/rotate_logs.zsh"
CLEAN_SCRIPT="${REPO_ROOT}/scripts/ops/clean_cache.zsh"
REBUILD_DEV_ENV_SCRIPT="${REPO_ROOT}/scripts/ops/rebuild_dev_env.zsh"

LABEL_DEFAULT="local.apple-notes-snapshot"
LABEL="${NOTES_SNAPSHOT_LAUNCHD_LABEL:-$LABEL_DEFAULT}"
WEB_LABEL_DEFAULT="${LABEL}.webui"
WEB_LABEL="${NOTES_SNAPSHOT_LAUNCHD_WEB_LABEL:-$WEB_LABEL_DEFAULT}"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
PLIST_TARGET_PATH="${LAUNCHD_DIR}/${LABEL}.plist"
WEB_PLIST_TARGET_PATH="${LAUNCHD_DIR}/${WEB_LABEL}.plist"

LIB_COMMON="${REPO_ROOT}/scripts/lib/common.zsh"
LIB_CONFIG="${REPO_ROOT}/scripts/lib/config.zsh"
LIB_LAUNCHD="${REPO_ROOT}/scripts/lib/launchd.zsh"
CMD_DIR="${REPO_ROOT}/scripts/cmd"

if [[ ! -f "$LIB_COMMON" ]]; then
  echo "missing lib/common: $LIB_COMMON" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$LIB_COMMON"

if [[ ! -f "$LIB_CONFIG" ]]; then
  die "missing lib/config: $LIB_CONFIG"
fi

# shellcheck disable=SC1090
source "$LIB_CONFIG"

if [[ ! -f "$LIB_LAUNCHD" ]]; then
  die "missing lib/launchd: $LIB_LAUNCHD"
fi

# shellcheck disable=SC1090
source "$LIB_LAUNCHD"

CMD_FILES=(
  "${CMD_DIR}/launchd.zsh"
  "${CMD_DIR}/vendor.zsh"
  "${CMD_DIR}/ops.zsh"
  "${CMD_DIR}/flows.zsh"
)

for cmd_file in "${CMD_FILES[@]}"; do
  if [[ ! -f "$cmd_file" ]]; then
    die "missing command module: $cmd_file"
  fi
  # shellcheck disable=SC1090
  source "$cmd_file"
done

usage() {
  cat <<'USAGE'
Apple Notes Snapshot - notesctl (single entrypoint)

Usage:
  ./notesctl [command] [args]
  ./notesctl help [command]

Recommended first run:
  1. Review config/notes_snapshot.env
     Default export destination: $HOME/iCloudDrive/NotesSnapshots
  2. ./notesctl run --no-status
  3. ./notesctl install --minutes 30 --load
  4. ./notesctl verify
     ./notesctl doctor

This is a 3-step, about-3-minute setup path for most people.
The first run may trigger Apple Notes / AppleScript permission prompts.

Primary user lane:
  menu                    interactive menu (default)
  run                     run snapshot now
  install                 generate/install launchd plist (pass --web/--no-web)
  status                  status (pass --brief/--full/--verbose/--json/--tail)
  verify                  check last_success freshness
  doctor                  full sanity check (pass --json)
  permissions             show macOS permissions checklist
  web                     start the local Web UI + token-gated Local Web API (pass --host/--port)
  logs                    follow logs (pass --tail/--since/--stdout/--stderr/--launchd)
  log-health              scan logs and summarize error signals (pass --json)
  dashboard               show dashboard (metrics + phases)
  aggregate               aggregate runs from metrics/structured logs (pass --metrics/--structured/--tail)
  help                    show this help

Optional AI and agent-facing surfaces:
  ai-diagnose             operator next-step assistant for status/doctor/log-health summary
  mcp                     start the stdio-first MCP provider for MCP-aware hosts

Maintainer lane:
  setup                   maintainer bootstrap (vendor refresh + run + install + verify + doctor)
  self-heal               fix + run + verify + doctor
  fix                     fast fix (no doctor)
  ensure                  enforce 30-minute interval
  audit                   security configuration audit (pass --json)
  clean-cache             preview/remove local caches (pass --dry-run to preview)
  runtime-audit           inspect repo-local and external repo-owned runtime/cache residue
  clean-runtime           preview/remove external repo-owned runtime/cache residue
  browser-bootstrap       bootstrap the isolated Chrome root from the default Chrome root
  browser-open            launch or attach to the single repo-owned Chrome instance
  browser-contract        validate the isolated root + single instance + CDP attach-first contract
  rebuild-dev-env         rebuild a clean path-agnostic local virtual environment (Python 3.11+)
  update-vendor           refresh vendor (pass --ref, --patch-dry-run)
  update-vendor-commit    refresh vendor + auto-commit
  bootstrap               alias for update-vendor
  rotate-logs             rotate logs now (pass --max-bytes/--backups/--stdout/--stderr/--launchd/--webui/--metrics/--structured)

Examples:
  ./notesctl run --no-status
  ./notesctl install --minutes 30 --load
  ./notesctl status --brief
  ./notesctl log-health --tail 200
  ./notesctl ai-diagnose
  ./notesctl web --host 127.0.0.1 --port 8080
  ./notesctl mcp
  ./notesctl audit --json
  ./notesctl runtime-audit --json
  ./notesctl clean-runtime --dry-run
  ./notesctl browser-bootstrap --json
  ./notesctl browser-open --json
  ./notesctl browser-contract --json
  ./notesctl clean-cache --dry-run
  ./notesctl help run
  ./notesctl help install
  ./notesctl help web
  ./notesctl help audit
USAGE
}

is_help_request() {
  local arg="${1:-}"
  [[ "$arg" == "-h" || "$arg" == "--help" ]]
}

show_command_help() {
  local topic="${1:-}"
  case "$topic" in
    setup|perfect-setup)
      cmd_setup_help
      ;;
    run|run-now)
      cmd_run_help
      ;;
    status)
      cmd_status_help
      ;;
    verify)
      cmd_verify_help
      ;;
    doctor)
      cmd_doctor_help
      ;;
    audit)
      cmd_audit_help
      ;;
    runtime-audit)
      cmd_runtime_audit_help
      ;;
    clean-runtime)
      cmd_clean_runtime_help
      ;;
    browser-bootstrap)
      cmd_browser_bootstrap_help
      ;;
    browser-open)
      cmd_browser_open_help
      ;;
    ai-diagnose)
      cmd_ai_diagnose_help
      ;;
    browser-contract)
      cmd_browser_contract_help
      ;;
    mcp)
      cmd_mcp_help
      ;;
    install)
      cmd_install_help
      ;;
    clean-cache)
      cmd_clean_cache_help
      ;;
    rebuild-dev-env)
      cmd_rebuild_dev_env_help
      ;;
    permissions)
      cmd_permissions_help
      ;;
    web)
      cmd_web_help
      ;;
    "" )
      usage
      ;;
    *)
      warn "Unknown help topic: $topic"
      usage
      return 1
      ;;
  esac
}

# ------------------------------
# Command dispatch
# ------------------------------
cmd="${1:-menu}"
if [[ $# -gt 0 ]]; then
  shift || true
fi

case "$cmd" in
  menu)
    cmd_menu "$@"
    ;;
  setup|perfect-setup)
    if is_help_request "${1:-}"; then
      cmd_setup_help
    else
      cmd_setup "$@"
    fi
    ;;
  self-heal|heal)
    cmd_self_heal "$@"
    ;;
  fix|fast-fix)
    cmd_fix "$@"
    ;;
  ensure|ensure-30min)
    cmd_ensure "$@"
    ;;
  run|run-now)
    if is_help_request "${1:-}"; then
      cmd_run_help
    else
      cmd_run "$@"
    fi
    ;;
  status)
    if is_help_request "${1:-}"; then
      cmd_status_help
    else
      cmd_status "$@"
    fi
    ;;
  verify)
    if is_help_request "${1:-}"; then
      cmd_verify_help
    else
      cmd_verify "$@"
    fi
    ;;
  doctor)
    if is_help_request "${1:-}"; then
      cmd_doctor_help
    else
      cmd_doctor "$@"
    fi
    ;;
  audit)
    if is_help_request "${1:-}"; then
      cmd_audit_help
    else
      cmd_audit "$@"
    fi
    ;;
  runtime-audit)
    if is_help_request "${1:-}"; then
      cmd_runtime_audit_help
    else
      cmd_runtime_audit "$@"
    fi
    ;;
  clean-runtime)
    if is_help_request "${1:-}"; then
      cmd_clean_runtime_help
    else
      cmd_clean_runtime "$@"
    fi
    ;;
  browser-bootstrap)
    if is_help_request "${1:-}"; then
      cmd_browser_bootstrap_help
    else
      cmd_browser_bootstrap "$@"
    fi
    ;;
  browser-open)
    if is_help_request "${1:-}"; then
      cmd_browser_open_help
    else
      cmd_browser_open "$@"
    fi
    ;;
  permissions)
    if is_help_request "${1:-}"; then
      cmd_permissions_help
    else
      cmd_permissions "$@"
    fi
    ;;
  logs|tail)
    cmd_logs "$@"
    ;;
  dashboard)
    cmd_dashboard "$@"
    ;;
  aggregate)
    cmd_aggregate "$@"
    ;;
  ai-diagnose)
    if is_help_request "${1:-}"; then
      cmd_ai_diagnose_help
    else
      cmd_ai_diagnose "$@"
    fi
    ;;
  browser-contract)
    if is_help_request "${1:-}"; then
      cmd_browser_contract_help
    else
      cmd_browser_contract "$@"
    fi
    ;;
  mcp)
    if is_help_request "${1:-}"; then
      cmd_mcp_help
    else
      cmd_mcp "$@"
    fi
    ;;
  web)
    if is_help_request "${1:-}"; then
      cmd_web_help
    else
      cmd_web "$@"
    fi
    ;;
  log-health)
    cmd_log_health "$@"
    ;;
  clean-cache)
    if is_help_request "${1:-}"; then
      cmd_clean_cache_help
    else
      cmd_clean_cache "$@"
    fi
    ;;
  rebuild-dev-env)
    if is_help_request "${1:-}"; then
      cmd_rebuild_dev_env_help
    else
      cmd_rebuild_dev_env "$@"
    fi
    ;;
  update-vendor)
    cmd_update_vendor "$@"
    ;;
  update-vendor-commit)
    cmd_update_vendor_commit "$@"
    ;;
  bootstrap|vendor-bootstrap)
    cmd_update_vendor "$@"
    ;;
  install)
    if is_help_request "${1:-}"; then
      cmd_install_help
    else
      cmd_install "$@"
    fi
    ;;
  rotate-logs)
    cmd_rotate_logs "$@"
    ;;
  help|-h|--help)
    show_command_help "${1:-}"
    ;;
  *)
    warn "Unknown command: $cmd"
    usage
    exit 1
    ;;
esac
