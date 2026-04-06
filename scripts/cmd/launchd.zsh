#!/bin/zsh

# ------------------------------
# Launchd commands (sourced)
# ------------------------------
launchd_write_exec_bridge() {
  local bridge_path="$1"
  local exec_bin="$2"
  local target_script="$3"

  "$MKDIR_BIN" -p -- "${bridge_path:h}"
  cat > "$bridge_path" <<EOF
#!/bin/zsh
set -euo pipefail
exec "${exec_bin}" "${target_script}" "\$@"
EOF
  chmod 755 "$bridge_path"
}

launchd_write_script_bridge() {
  local bridge_path="$1"
  local runtime_repo_root="$2"
  local runtime_log_dir="$3"
  local runtime_lock_dir="$4"
  local runtime_lock_file="$5"
  local runtime_state_dir="$6"
  local target_script="$7"
  local preferred_python="${8:-}"

  local python_export=""
  if [[ -n "$preferred_python" ]]; then
    python_export=$'export NOTES_SNAPSHOT_PYTHON_BIN="'"$preferred_python"$'"\n'
  fi

  "$MKDIR_BIN" -p -- "${bridge_path:h}"
  cat > "$bridge_path" <<EOF
#!/bin/zsh
set -euo pipefail
export PATH="${runtime_repo_root}/bin:/usr/bin:/bin:/usr/sbin:/sbin"
${python_export}export NOTES_SNAPSHOT_REPO_ROOT="${runtime_repo_root}"
export NOTES_SNAPSHOT_DIR="${runtime_repo_root}/vendor/notes-exporter"
export NOTES_SNAPSHOT_LOG_DIR="${runtime_log_dir}"
export NOTES_SNAPSHOT_LOCK_DIR="${runtime_lock_dir}"
export NOTES_SNAPSHOT_LOCK_FILE="${runtime_lock_file}"
export NOTES_SNAPSHOT_STATE_DIR="${runtime_state_dir}"
exec /bin/zsh "${target_script}" "\$@"
EOF
  chmod 755 "$bridge_path"
}

launchd_write_python_shim() {
  local runtime_repo_root="$1"
  local preferred_python="${2:-}"
  local shim_dir="${runtime_repo_root}/bin"
  local shim_path="${shim_dir}/python"

  "$MKDIR_BIN" -p -- "$shim_dir"
  cat > "$shim_path" <<EOF
#!/bin/zsh
set -euo pipefail

for candidate in "${preferred_python}" /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if [[ -z "\$candidate" ]]; then
    continue
  fi
  if [[ -x "\$candidate" ]]; then
    exec "\$candidate" "\$@"
  fi
done

if command -v python3 >/dev/null 2>&1; then
  exec "\$(command -v python3)" "\$@"
fi

echo "python3 not found" >&2
exit 127
EOF
  chmod 755 "$shim_path"
}

launchd_remove_tree() {
  local target="$1"
  if [[ -z "$target" ]]; then
    return 0
  fi
  if [[ ! -e "$target" && ! -L "$target" ]]; then
    return 0
  fi

  "$RM_BIN" -rf -- "$target" 2>/dev/null || true
  if [[ ! -e "$target" && ! -L "$target" ]]; then
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    python3 - "$target" <<'PY' >/dev/null 2>&1 || true
import pathlib
import shutil
import sys

target = pathlib.Path(sys.argv[1])
try:
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)
except Exception:
    raise SystemExit(1)
PY
  fi

  if [[ ! -e "$target" && ! -L "$target" ]]; then
    return 0
  fi

  sleep 1
  "$RM_BIN" -rf -- "$target"
}

launchd_prepare_runtime_repo() {
  local runtime_root="$1"
  local target_repo="$2"
  local preferred_python="${3:-}"

  launchd_remove_tree "$runtime_root" || die "failed to remove runtime repo root: $runtime_root"
  "$MKDIR_BIN" -p -- "$runtime_root"

  local entry=""
  for entry in config scripts vendor web; do
    if [[ -e "${target_repo}/${entry}" ]]; then
      cp -R "${target_repo}/${entry}" "${runtime_root}/${entry}"
    fi
  done
  if [[ -f "${target_repo}/notesctl" ]]; then
    cp -f -- "${target_repo}/notesctl" "${runtime_root}/notesctl"
    chmod 755 "${runtime_root}/notesctl"
  fi
  launchd_write_python_shim "$runtime_root" "$preferred_python"
  if [[ -f "${runtime_root}/scripts/core/notes_snapshot_wrapper.zsh" ]]; then
    chmod 755 "${runtime_root}/scripts/core/notes_snapshot_wrapper.zsh"
  fi
}

launchd_sync_runtime_venv() {
  local source_venv="$1"
  local runtime_venv="$2"

  if [[ ! -d "$source_venv" || ! -x "${source_venv}/bin/python" ]]; then
    return 0
  fi

  launchd_remove_tree "$runtime_venv" || die "failed to remove runtime venv: $runtime_venv"
  "$MKDIR_BIN" -p -- "${runtime_venv:h}"
  cp -R "$source_venv" "$runtime_venv"
}

launchd_link_runtime_dir() {
  local link_path="$1"
  local target_path="$2"

  "$MKDIR_BIN" -p -- "${link_path:h}" "$target_path"
  if [[ -L "$link_path" ]]; then
    "$RM_BIN" -f -- "$link_path"
  elif [[ -d "$link_path" ]]; then
    cp -R "${link_path}/." "$target_path/" 2>/dev/null || true
    launchd_remove_tree "$link_path" || die "failed to replace runtime link path: $link_path"
  elif [[ -e "$link_path" ]]; then
    "$RM_BIN" -f -- "$link_path"
  fi
  ln -s "$target_path" "$link_path"
}

launchd_label_safe_name() {
  local raw_label="$1"
  raw_label="${raw_label//[^A-Za-z0-9._-]/_}"
  printf '%s' "$raw_label"
}

launchd_service_loaded() {
  local domain="$1"
  local label="$2"
  launchctl print "$domain/$label" >/dev/null 2>&1
}

launchd_retire_instance() {
  local domain="$1"
  local label="$2"
  if [[ -z "$label" ]]; then
    return 0
  fi

  local instance_key
  instance_key="$(launchd_label_safe_name "$label")"
  local plist_path="${LAUNCHD_DIR}/${label}.plist"
  local launchd_bridge_dir="$(launchd_bridge_root)/${instance_key}"
  local runtime_repo_root
  runtime_repo_root="$(launchd_runtime_repo_root "$instance_key")"

  if [[ -f "$plist_path" ]]; then
    launchctl bootout "$domain" "$plist_path" >/dev/null 2>&1 || true
  else
    launchctl bootout "$domain/$label" >/dev/null 2>&1 || true
  fi
  launchctl disable "$domain/$label" >/dev/null 2>&1 || true
  "$RM_BIN" -f -- "$plist_path"
  launchd_remove_tree "$launchd_bridge_dir" || die "failed to remove launchd bridge dir: $launchd_bridge_dir"
  launchd_remove_tree "$runtime_repo_root" || die "failed to remove runtime repo root: $runtime_repo_root"
}

cmd_install_help() {
  cat <<'HELP'
Install = generate the launchd plist and optionally load it.

This is step 3 of the public first-successful-run path:
  1. review config/notes_snapshot.env
  2. ./notesctl run --no-status
  3. ./notesctl install --minutes 30 --load
  4. ./notesctl verify
     ./notesctl doctor

Use this after the first manual snapshot succeeds so launchd can keep the
backup loop running on the configured interval.

Options:
  --interval <sec>     override the generated interval in seconds
  --minutes <minutes>  override the generated interval in minutes
  --load               load the plist into launchd after generating it
  --unload             boot out the existing plist before returning
  --status             print the full status report after install actions
  --status-brief       print the brief status report after install actions
  --web                also generate and manage the optional local Web UI plist
  --no-web             skip the Web UI plist even if it is enabled in config

Examples:
  ./notesctl install --minutes 30 --load
  ./notesctl install --minutes 30 --load --web
HELP
}

cmd_install() {
  if ! command -v launchctl >/dev/null 2>&1; then
    die "launchctl not found; required for launchd install"
  fi

  load_env_with_defaults
  run_repo_local_cache_janitor
  run_external_cache_janitor
  local lib_state="${REPO_ROOT}/scripts/lib/state.zsh"
  if [[ -f "$lib_state" ]]; then
    # shellcheck disable=SC1090
    source "$lib_state"
  fi

  local interval_sec
  validate_int "NOTES_SNAPSHOT_INTERVAL_MINUTES" "$NOTES_SNAPSHOT_INTERVAL_MINUTES"
  interval_sec=$(( NOTES_SNAPSHOT_INTERVAL_MINUTES * 60 ))

  local do_load=0
  local do_unload=0
  local do_status=0
  local status_brief=0
  local web_enable="${NOTES_SNAPSHOT_WEB_ENABLE}"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --interval)
        interval_sec="$2"
        shift 2
        ;;
      --minutes)
        interval_sec=$(( $2 * 60 ))
        shift 2
        ;;
      --load)
        do_load=1
        shift
        ;;
      --unload)
        do_unload=1
        shift
        ;;
      --status)
        do_status=1
        shift
        ;;
      --status-brief)
        do_status=1
        status_brief=1
        shift
        ;;
      --web)
        web_enable=1
        shift
        ;;
      --no-web)
        web_enable=0
        shift
        ;;
      *)
        die "unknown arg: $1"
        ;;
    esac
  done

  validate_int "interval_sec" "$interval_sec"
  require_file "$WRAPPER_SCRIPT"

  if [[ -n "${NOTES_SNAPSHOT_LAUNCHD_WATCH_PATHS}" || -n "${NOTES_SNAPSHOT_LAUNCHD_QUEUE_DIRS}" ]]; then
    info "WatchPaths/QueueDirectories enabled; treat them as accelerators, keep schedule as primary trigger."
    if [[ -z "${NOTES_SNAPSHOT_LAUNCHD_THROTTLE_SEC}" ]]; then
      NOTES_SNAPSHOT_LAUNCHD_THROTTLE_SEC="60"
      info "ThrottleInterval not set; defaulting to 60s for event triggers."
    fi
  fi

  local schedule_block
  schedule_block="$(launchd_build_schedule_block "$interval_sec" "$NOTES_SNAPSHOT_CALENDAR_MINUTES")"

  local watch_block=""
  watch_block="$(launchd_build_paths_block "WatchPaths" "$NOTES_SNAPSHOT_LAUNCHD_WATCH_PATHS")"

  local queue_block=""
  queue_block="$(launchd_build_paths_block "QueueDirectories" "$NOTES_SNAPSHOT_LAUNCHD_QUEUE_DIRS")"

  local throttle_block=""
  throttle_block="$(launchd_build_throttle_block "$NOTES_SNAPSHOT_LAUNCHD_THROTTLE_SEC")"

  local generated_dir="${REPO_ROOT}/generated/launchd"
  local launchd_instance_key
  launchd_instance_key="$(launchd_label_safe_name "$LABEL")"
  local launchd_bridge_root_dir
  launchd_bridge_root_dir="$(launchd_bridge_root)"
  local launchd_bridge_dir="${launchd_bridge_root_dir}/${launchd_instance_key}"
  local runtime_repo_root
  runtime_repo_root="$(launchd_runtime_repo_root "$launchd_instance_key")"
  local runtime_data_root
  runtime_data_root="$(launchd_runtime_data_root "$launchd_instance_key")"
  local runtime_log_dir="${runtime_data_root}/logs"
  local runtime_venv_dir="${runtime_data_root}/venv"
  local runtime_cache_root="${runtime_data_root}/cache/apple-notes-snapshot"
  local runtime_state_dir="${runtime_cache_root}/state"
  local runtime_lock_root="${runtime_cache_root}/lock"
  local runtime_lock_dir="${runtime_lock_root}/mkdir"
  local runtime_lock_file="${runtime_lock_root}/flock.lock"
  local runtime_wrapper_path="${runtime_repo_root}/scripts/core/notes_snapshot_wrapper.zsh"
  local runtime_web_script_path="${runtime_repo_root}/scripts/ops/web_server.py"
  local preferred_runtime_python=""
  local source_dev_venv="${REPO_ROOT}/.runtime-cache/dev/venv"
  local repo_log_dir="${NOTES_SNAPSHOT_LOG_DIR}"
  local repo_state_dir="${NOTES_SNAPSHOT_STATE_DIR}"
  local repo_lock_root="${NOTES_SNAPSHOT_LOCK_FILE:h}"
  local launchd_wrapper_bridge="${launchd_bridge_dir}/apple-notes-snapshot-wrapper.zsh"
  local launchd_web_bridge="${launchd_bridge_dir}/apple-notes-snapshot-webui.zsh"
  "$MKDIR_BIN" -p -- "$LAUNCHD_DIR" "$generated_dir" "$launchd_bridge_dir" "$runtime_log_dir" "$runtime_state_dir" "$runtime_lock_root"
  launchd_sync_runtime_venv "$source_dev_venv" "$runtime_venv_dir"
  if [[ -x "${runtime_venv_dir}/bin/python" ]]; then
    preferred_runtime_python="${runtime_venv_dir}/bin/python"
  fi
  launchd_prepare_runtime_repo "$runtime_repo_root" "$REPO_ROOT" "$preferred_runtime_python"
  launchd_link_runtime_dir "$repo_log_dir" "$runtime_log_dir"
  launchd_link_runtime_dir "$repo_state_dir" "$runtime_state_dir"
  launchd_link_runtime_dir "$repo_lock_root" "$runtime_lock_root"
  chmod 755 "$WRAPPER_SCRIPT"
  launchd_write_script_bridge "$launchd_wrapper_bridge" "$runtime_repo_root" "$runtime_log_dir" "$runtime_lock_dir" "$runtime_lock_file" "$runtime_state_dir" "$runtime_wrapper_path" "$preferred_runtime_python"

  local plist_repo_path="${generated_dir}/${LABEL}.plist"
  local plist_target_path="${LAUNCHD_DIR}/${LABEL}.plist"

  launchd_write_plist \
    "$plist_repo_path" \
    "$LABEL" \
    "$launchd_wrapper_bridge" \
    "$runtime_log_dir" \
    "$schedule_block" \
    "$watch_block" \
    "$queue_block" \
    "$throttle_block"

  cp -f -- "$plist_repo_path" "$plist_target_path"

  local domain="gui/$(id -u)"

  if [[ "$do_unload" -eq 1 ]]; then
    launchctl bootout "$domain" "$plist_target_path" >/dev/null 2>&1 || true
  fi

  if [[ "$do_load" -eq 1 ]]; then
    launchctl bootout "$domain" "$plist_target_path" >/dev/null 2>&1 || true
    launchctl enable "$domain/$LABEL"
    if ! launchctl bootstrap "$domain" "$plist_target_path"; then
      launchd_service_loaded "$domain" "$LABEL" || return $?
    fi
    # RunAtLoad on the plist already starts the first run after bootstrap.
    # Avoid a second immediate kickstart that can race the first run and leave
    # a duplicate "already running" ledger entry behind.
  fi

  if [[ "$web_enable" -eq 1 ]]; then
    local py=""
    if command -v state_find_python >/dev/null 2>&1; then
      py="$(state_find_python)" || true
    fi
    if [[ -z "$py" ]]; then
      warn "python3/python not found; skip web ui install"
      web_enable=0
    else
      if command -v "$py" >/dev/null 2>&1; then
        py="$(command -v "$py")"
      fi
    fi
  fi

  if [[ "$web_enable" -eq 1 ]]; then
    local web_script="${REPO_ROOT}/scripts/ops/web_server.py"
    require_file "$web_script"
    launchd_write_exec_bridge "$launchd_web_bridge" "$py" "$runtime_web_script_path"

    if [[ "${NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN}" == "1" ]] && [[ -z "${NOTES_SNAPSHOT_WEB_TOKEN}" ]]; then
      die "NOTES_SNAPSHOT_WEB_TOKEN is required when NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN=1"
    fi

    validate_int "NOTES_SNAPSHOT_WEB_PORT" "$NOTES_SNAPSHOT_WEB_PORT"
    if [[ "$NOTES_SNAPSHOT_WEB_PORT" -lt 1 || "$NOTES_SNAPSHOT_WEB_PORT" -gt 65535 ]]; then
      die "NOTES_SNAPSHOT_WEB_PORT out of range: $NOTES_SNAPSHOT_WEB_PORT"
    fi

    local web_plist_repo_path="${generated_dir}/${WEB_LABEL}.plist"
    local web_plist_target_path="$WEB_PLIST_TARGET_PATH"
    launchd_write_web_plist \
      "$web_plist_repo_path" \
      "$WEB_LABEL" \
      "/bin/zsh" \
      "$launchd_web_bridge" \
      "$runtime_log_dir" \
      "$NOTES_SNAPSHOT_WEB_HOST" \
      "$NOTES_SNAPSHOT_WEB_PORT" \
      "$NOTES_SNAPSHOT_WEB_CMD_TIMEOUT_SEC" \
      "$runtime_repo_root" \
      "$runtime_state_dir" \
      "$NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN" \
      "$NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN_FOR_STATIC" \
      "$NOTES_SNAPSHOT_WEB_TOKEN" \
      "$NOTES_SNAPSHOT_WEB_ALLOW_REMOTE" \
      "$NOTES_SNAPSHOT_WEB_ALLOW_IPS" \
      "$NOTES_SNAPSHOT_WEB_TOKEN_SCOPES" \
      "$NOTES_SNAPSHOT_WEB_READONLY" \
      "$NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW" \
      "$NOTES_SNAPSHOT_WEB_MAX_TAIL_LINES" \
      "$NOTES_SNAPSHOT_WEB_RATE_LIMIT_WINDOW_SEC" \
      "$NOTES_SNAPSHOT_WEB_RATE_LIMIT_MAX" \
      "$NOTES_SNAPSHOT_WEB_ACTION_COOLDOWNS"

    cp -f -- "$web_plist_repo_path" "$web_plist_target_path"

    if [[ "$do_unload" -eq 1 ]]; then
      launchctl bootout "$domain" "$web_plist_target_path" >/dev/null 2>&1 || true
    fi
    if [[ "$do_load" -eq 1 ]]; then
      launchctl bootout "$domain" "$web_plist_target_path" >/dev/null 2>&1 || true
      launchctl enable "$domain/$WEB_LABEL"
      if ! launchctl bootstrap "$domain" "$web_plist_target_path"; then
        launchd_service_loaded "$domain" "$WEB_LABEL" || return $?
      fi
      # RunAtLoad on the web plist is enough after bootstrap; avoid a redundant
      # second kickstart against the same just-bootstrapped service.
    fi
  else
    if [[ "$do_unload" -eq 1 ]] && [[ -f "$WEB_PLIST_TARGET_PATH" ]]; then
      launchctl bootout "$domain" "$WEB_PLIST_TARGET_PATH" >/dev/null 2>&1 || true
    fi
  fi

  if [[ "$do_status" -eq 1 ]] && [[ -x "$STATUS_SCRIPT" ]]; then
    if [[ "$status_brief" -eq 1 ]]; then
      "$STATUS_SCRIPT" --brief
    else
      "$STATUS_SCRIPT"
    fi
  fi
}

cmd_ensure() {
  load_env_with_defaults
  run_repo_local_cache_janitor
  run_external_cache_janitor
  validate_int "NOTES_SNAPSHOT_INTERVAL_MINUTES" "$NOTES_SNAPSHOT_INTERVAL_MINUTES"

  local output_json=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --json)
        output_json=1
        shift
        ;;
      *)
        die "unknown arg: $1"
        ;;
    esac
  done

  emit_info() {
    if [[ "$output_json" -eq 0 ]]; then
      info "$1"
    fi
  }

  local expected_interval=$(( NOTES_SNAPSHOT_INTERVAL_MINUTES * 60 ))
  local current_interval=""
  local current_calendar=""
  local calendar_minutes="${NOTES_SNAPSHOT_CALENDAR_MINUTES}"
  local current_calendar_minutes=""
  local mode=""
  local needs_reinstall=0
  local reinstalled=0
  local action="ok"
  local reason=""

  if [[ -f "$PLIST_TARGET_PATH" ]] && command -v plutil >/dev/null 2>&1; then
    current_interval=$(plutil -extract StartInterval raw -o - "$PLIST_TARGET_PATH" 2>/dev/null || true)
    current_calendar=$(plutil -extract StartCalendarInterval xml1 -o - "$PLIST_TARGET_PATH" 2>/dev/null || true)
    if [[ -n "$current_calendar" ]]; then
      current_calendar_minutes=$(printf '%s' "$current_calendar" | sed -n 's/.*<integer>\([0-9]\+\)<\/integer>.*/\1/p' | tr '\n' ',' | sed 's/,$//')
    fi
  fi

  if [[ -n "$calendar_minutes" ]]; then
    mode="calendar"
    if [[ -z "$current_calendar" ]]; then
      needs_reinstall=1
    else
      local -a minutes_list
      minutes_list=(${(s:,:)calendar_minutes})
      for minute in "${minutes_list[@]}"; do
        local trimmed
        trimmed="$(launchd_trim "$minute")"
        if [[ -z "$trimmed" ]]; then
          continue
        fi
        if [[ ! "$trimmed" =~ ^[0-9]+$ ]]; then
          die "invalid calendar minute: $trimmed"
        fi
        if [[ "$current_calendar" != *"<integer>${trimmed}</integer>"* ]]; then
          needs_reinstall=1
          reason="calendar_mismatch"
          break
        fi
      done
    fi
    if [[ "$needs_reinstall" -eq 1 ]]; then
      emit_info "StartCalendarInterval mismatch or missing; reinstalling (minutes=${calendar_minutes})"
      if [[ "$output_json" -eq 1 ]]; then
        cmd_install --minutes "$NOTES_SNAPSHOT_INTERVAL_MINUTES" --load >/dev/null
      else
        cmd_install --minutes "$NOTES_SNAPSHOT_INTERVAL_MINUTES" --load
      fi
      reinstalled=1
      action="reinstalled"
    else
      emit_info "OK: StartCalendarInterval set to minutes=${calendar_minutes}"
    fi
  elif [[ "$expected_interval" -eq 1800 ]]; then
    mode="calendar"
    if [[ -z "$current_calendar" ]] \
      || [[ "$current_calendar" != *"<integer>0</integer>"* ]] \
      || [[ "$current_calendar" != *"<integer>30</integer>"* ]]; then
      needs_reinstall=1
      reason="calendar_mismatch"
      emit_info "StartCalendarInterval mismatch or missing; reinstalling (expected minutes=0,30)"
      if [[ "$output_json" -eq 1 ]]; then
        cmd_install --minutes "$NOTES_SNAPSHOT_INTERVAL_MINUTES" --load >/dev/null
      else
        cmd_install --minutes "$NOTES_SNAPSHOT_INTERVAL_MINUTES" --load
      fi
      reinstalled=1
      action="reinstalled"
    else
      emit_info "OK: StartCalendarInterval set to :00/:30"
    fi
  else
    mode="interval"
    if [[ -z "$current_interval" ]] || [[ "$current_interval" -ne "$expected_interval" ]]; then
      needs_reinstall=1
      reason="interval_mismatch"
      emit_info "StartInterval mismatch or missing; reinstalling (expected=${expected_interval})"
      if [[ "$output_json" -eq 1 ]]; then
        cmd_install --minutes "$NOTES_SNAPSHOT_INTERVAL_MINUTES" --load >/dev/null
      else
        cmd_install --minutes "$NOTES_SNAPSHOT_INTERVAL_MINUTES" --load
      fi
      reinstalled=1
      action="reinstalled"
    else
      emit_info "OK: StartInterval is ${current_interval}s"
    fi
  fi

  if [[ -f "$PLIST_TARGET_PATH" ]] && command -v plutil >/dev/null 2>&1; then
    local watch_xml=""
    local queue_xml=""
    local watch_paths=""
    local queue_dirs=""
    local throttle_interval=""

    watch_xml=$(plutil -extract WatchPaths xml1 -o - "$PLIST_TARGET_PATH" 2>/dev/null || true)
    queue_xml=$(plutil -extract QueueDirectories xml1 -o - "$PLIST_TARGET_PATH" 2>/dev/null || true)
    throttle_interval=$(plutil -extract ThrottleInterval raw -o - "$PLIST_TARGET_PATH" 2>/dev/null || true)

    if [[ -n "$watch_xml" ]]; then
      watch_paths=$(printf '%s' "$watch_xml" | sed -n 's/.*<string>\(.*\)<\/string>.*/\1/p' | tr '\n' ',' | sed 's/,$//')
    fi
    if [[ -n "$queue_xml" ]]; then
      queue_dirs=$(printf '%s' "$queue_xml" | sed -n 's/.*<string>\(.*\)<\/string>.*/\1/p' | tr '\n' ',' | sed 's/,$//')
    fi

    emit_info "WatchPaths: ${watch_paths:-"(none)"}"
    emit_info "QueueDirectories: ${queue_dirs:-"(none)"}"
    emit_info "ThrottleInterval: ${throttle_interval:-"(none)"}"
  fi

  if [[ "$output_json" -eq 1 ]]; then
    local current_interval_json="null"
    if [[ -n "$current_interval" ]] && [[ "$current_interval" =~ ^[0-9]+$ ]]; then
      current_interval_json="$current_interval"
    fi
    local needs_reinstall_json="false"
    local reinstalled_json="false"
    local plist_exists="false"
    if [[ "$needs_reinstall" -eq 1 ]]; then
      needs_reinstall_json="true"
    fi
    if [[ "$reinstalled" -eq 1 ]]; then
      reinstalled_json="true"
    fi
    if [[ -f "$PLIST_TARGET_PATH" ]]; then
      plist_exists="true"
    fi
    json_escape() {
      local value="$1"
      value="${value//\\/\\\\}"
      value="${value//\"/\\\"}"
      printf '%s' "$value"
    }
    cat <<JSON
{
  "mode": "$(json_escape "$mode")",
  "expected_interval_sec": $expected_interval,
  "expected_calendar_minutes": "$(json_escape "$calendar_minutes")",
  "current_interval_sec": $current_interval_json,
  "current_calendar_minutes": "$(json_escape "$current_calendar_minutes")",
  "needs_reinstall": $needs_reinstall_json,
  "reinstalled": $reinstalled_json,
  "action": "$(json_escape "$action")",
  "reason": "$(json_escape "$reason")",
  "watch_paths": "$(json_escape "${watch_paths:-}")",
  "queue_directories": "$(json_escape "${queue_dirs:-}")",
  "throttle_interval": "$(json_escape "${throttle_interval:-}")",
  "plist_path": "$(json_escape "$PLIST_TARGET_PATH")",
  "plist_exists": $plist_exists
}
JSON
  fi
}
