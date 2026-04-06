#!/bin/zsh

# ------------------------------
# Flow commands (sourced)
# ------------------------------
cmd_setup_help() {
  cat <<'HELP'
Setup = maintainer bootstrap.

What it does:
  - refreshes the vendored upstream
  - runs one snapshot unless --skip-run is used
  - installs / reloads launchd unless --skip-install is used
  - runs status + verify
  - runs doctor unless --skip-doctor is used

This is not the public first-run path.
If you are here to get your first successful snapshot, use:
  1. review config/notes_snapshot.env
  2. ./notesctl run --no-status
  3. ./notesctl install --minutes 30 --load
  4. ./notesctl verify
     ./notesctl doctor

Options:
  --ref <tag|branch|sha>  vendor ref to refresh
  --auto-commit           auto-commit vendor refresh
  --skip-run              skip the first snapshot run
  --skip-install          skip launchd install / ensure
  --skip-doctor           skip doctor after verify
  -h, --help              show this help
HELP
}

cmd_fix() {
  line
  info "Step 1/3: enforce 30-minute interval"
  cmd_ensure

  line
  info "Step 2/3: run snapshot now"
  cmd_run --no-status

  line
  info "Step 3/3: status + verify"
  cmd_status --full
  cmd_verify
}

cmd_self_heal() {
  line
  info "Step 1/4: enforce 30-minute interval"
  cmd_ensure

  line
  info "Step 2/4: run snapshot now"
  cmd_run --no-status

  line
  info "Step 3/4: status (brief)"
  cmd_status --brief

  line
  info "Step 4/4: verify + doctor"
  cmd_verify
  cmd_doctor
}

cmd_setup() {
  load_env_with_defaults

  local auto_commit=0
  local skip_run=0
  local skip_install=0
  local skip_doctor=0
  local ref=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        cmd_setup_help
        return 0
        ;;
      --auto-commit)
        auto_commit=1
        shift
        ;;
      --skip-run)
        skip_run=1
        shift
        ;;
      --skip-install)
        skip_install=1
        shift
        ;;
      --skip-doctor)
        skip_doctor=1
        shift
        ;;
      --ref)
        ref="$2"
        shift 2
        ;;
      *)
        die "unknown arg: $1"
        ;;
    esac
  done

  if [[ "$auto_commit" -eq 1 ]]; then
    if [[ -n "$ref" ]]; then
      cmd_update_vendor_commit --ref "$ref"
    else
      cmd_update_vendor_commit
    fi
  else
    if [[ -n "$ref" ]]; then
      cmd_update_vendor --ref "$ref"
    else
      cmd_update_vendor
    fi
  fi

  if [[ "$skip_run" -eq 0 ]]; then
    run_zsh "$WRAPPER_SCRIPT"
  fi

  if [[ "$skip_install" -eq 0 ]]; then
    cmd_install --minutes "$NOTES_SNAPSHOT_INTERVAL_MINUTES" --load
    cmd_ensure
  fi

  cmd_status --full
  cmd_verify

  if [[ "$skip_doctor" -eq 0 ]]; then
    cmd_doctor
  fi
}

cmd_menu() {
  line
  printf 'Apple Notes Snapshot - Quick Menu\n'
  line
  printf '1) Setup (maintainer bootstrap: vendor refresh + run + install + verify + doctor)\n'
  printf '2) Self-heal (fix + run + verify + doctor)\n'
  printf '3) Fast fix (ensure + run + verify)\n'
  printf '4) Ensure 30-minute interval\n'
  printf '5) Run snapshot now\n'
  printf '6) Verify OK (freshness)\n'
  printf '7) Status (brief)\n'
  printf '8) Status (full)\n'
  printf '9) Status (verbose)\n'
  printf '10) Doctor (full sanity check)\n'
  printf '11) Follow logs (live)\n'
  printf '12) Dashboard (metrics + phases)\n'
  printf '13) Update vendor and auto-commit\n'
  printf '14) Rotate logs now\n'
  printf '15) Log health (error summary)\n'
  printf '16) Web UI (local dashboard)\n'
  printf '0) Exit\n'
  line
  printf 'Tip: For the public first-run path, review config/notes_snapshot.env first,\n'
  printf 'then use ./notesctl run --no-status -> install --minutes 30 --load -> verify.\n'
  line
  printf 'Choose: '
  read -r choice

  if [[ -z "$choice" ]]; then
    info "No selection. Exiting."
    return 0
  fi

  case "$choice" in
    1)
      cmd_setup
      ;;
    2)
      cmd_self_heal
      ;;
    3)
      cmd_fix
      ;;
    4)
      cmd_ensure
      ;;
    5)
      cmd_run
      ;;
    6)
      cmd_verify
      ;;
    7)
      cmd_status --brief
      ;;
    8)
      cmd_status --full
      ;;
    9)
      cmd_status --verbose
      ;;
    10)
      cmd_doctor
      ;;
    11)
      cmd_logs
      ;;
    12)
      cmd_dashboard
      ;;
    13)
      printf '%s (y/N): ' "Update vendor and auto-commit?"
      read -r answer
      case "$answer" in
        y|Y|yes|YES)
          cmd_update_vendor_commit
          ;;
        *)
          info "Canceled."
          ;;
      esac
      ;;
    14)
      cmd_rotate_logs
      ;;
    15)
      cmd_log_health
      ;;
    16)
      cmd_web
      ;;
    0)
      info "Bye."
      ;;
    *)
      die "Unknown option: $choice"
      ;;
  esac
}
