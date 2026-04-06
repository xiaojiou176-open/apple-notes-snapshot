#!/bin/zsh

# ------------------------------
# Operational commands (sourced)
# ------------------------------
ensure_lib_state() {
  local lib_state="${REPO_ROOT}/scripts/lib/state.zsh"
  if [[ ! -f "$lib_state" ]]; then
    die "missing lib/state: $lib_state"
  fi
  # shellcheck disable=SC1090
  source "$lib_state"
}

run_repo_local_cache_janitor() {
  load_env_with_defaults
  local repo_root_abs="${REPO_ROOT:A}"
  local runtime_root_abs="${NOTES_SNAPSHOT_RUNTIME_ROOT:A}"
  local target=""
  local -a disposable_paths=(
    "${NOTES_SNAPSHOT_TEMP_DIR}"
    "${NOTES_SNAPSHOT_PYTHONPYCACHEPREFIX}"
    "${NOTES_SNAPSHOT_PYTEST_CACHE_DIR}"
    "${NOTES_SNAPSHOT_COVERAGE_FILE:h}"
    "${REPO_ROOT}/.pytest_cache"
    "${REPO_ROOT}/.coverage"
    "${REPO_ROOT}/tests/__pycache__"
    "${REPO_ROOT}/tests/unit/__pycache__"
    "${REPO_ROOT}/tests/e2e/__pycache__"
    "${REPO_ROOT}/scripts/ops/__pycache__"
    "${REPO_ROOT}/vendor/notes-exporter/__pycache__"
    "${REPO_ROOT}/vendor/notes-exporter/.pytest_cache"
  )

  repo_local_janitor_target_allowed() {
    local candidate="$1"
    case "$candidate" in
      "${runtime_root_abs}"|"${runtime_root_abs}"/*)
        return 0
        ;;
      "${repo_root_abs}/.pytest_cache"|\
      "${repo_root_abs}/.coverage"|\
      "${repo_root_abs}/tests/__pycache__"|\
      "${repo_root_abs}/tests/unit/__pycache__"|\
      "${repo_root_abs}/tests/e2e/__pycache__"|\
      "${repo_root_abs}/scripts/ops/__pycache__"|\
      "${repo_root_abs}/vendor/notes-exporter/__pycache__"|\
      "${repo_root_abs}/vendor/notes-exporter/.pytest_cache")
        return 0
        ;;
      *)
        return 1
        ;;
    esac
  }

  for target in "${disposable_paths[@]}"; do
    if [[ -z "$target" ]]; then
      continue
    fi
    local candidate="${target:A}"
    if ! repo_local_janitor_target_allowed "$candidate"; then
      continue
    fi
    if [[ -e "$candidate" ]]; then
      rm -rf -- "$candidate" >/dev/null 2>&1 || true
    fi
  done
}

run_external_cache_janitor() {
  load_env_with_defaults
  if [[ "${NOTES_SNAPSHOT_RUNTIME_AUTO_CLEAN}" != "1" ]]; then
    return 0
  fi

  ensure_lib_state
  local clean_script="${REPO_ROOT}/scripts/ops/clean_runtime.py"
  local py=""
  py="$(state_find_python)" || return 0
  if [[ -z "$py" ]]; then
    return 0
  fi
  require_file "$clean_script"

  "$py" "$clean_script" \
    --apply \
    --quiet-auto \
    --include-vendor-runtime \
    --retention-hours "${NOTES_SNAPSHOT_EXTERNAL_CACHE_TTL_HOURS}" \
    --browser-retention-hours "${NOTES_SNAPSHOT_BROWSER_CLONE_TTL_HOURS}" \
    --max-external-bytes "${NOTES_SNAPSHOT_EXTERNAL_CACHE_MAX_BYTES}" \
    --repo-root "${REPO_ROOT}" \
    --launchd-root "$(launchd_bridge_root)" \
    --runtime-root "$(launchd_runtime_root)" \
    --repos-root "$(launchd_repos_root)" \
    --legacy-launchd-root "$(launchd_legacy_launchd_root)" \
    --legacy-runtime-root "$(launchd_legacy_runtime_root)" \
    --legacy-repos-root "$(launchd_legacy_repos_root)" \
    --vendor-runtime-root "$(launchd_vendor_runtime_root)" \
    --legacy-vendor-runtime-root "$(launchd_legacy_vendor_runtime_root)" \
    --browser-root "$(launchd_browser_root)" \
    --browser-user-data-root "$(launchd_browser_user_data_root)" \
    --browser-temp-root "$(launchd_browser_temp_root)" \
    --current-label "${NOTES_SNAPSHOT_LAUNCHD_LABEL}" \
    --current-label "${NOTES_SNAPSHOT_LAUNCHD_WEB_LABEL}" >/dev/null 2>&1 || true
}

cmd_status_help() {
  cat <<'HELP'
Status = inspect the current snapshot state.

Use this when:
  - you want a quick read on freshness and launchd state
  - you want the human-facing health summary plus the config / launchd / ledger split
  - you want JSON output for tooling
  - you want to include recent tail lines in the report

Options:
  --brief              compact status summary
  --full               full status report (default)
  --verbose            include extra diagnostic detail
  --json               machine-readable status output
  --tail <lines>       override the configured tail line count

Examples:
  ./notesctl status --brief
  ./notesctl status --json
  ./notesctl status --full --tail 200
HELP
}

cmd_status() {
  run_zsh "$STATUS_SCRIPT" "$@"
}

cmd_permissions_help() {
  cat <<'HELP'
Permissions = print the manual macOS permission checklist.

Use this before the first run if you want the shortest explanation of:
  - Full Disk Access for your terminal
  - Automation permission to control Notes
  - how to respond when macOS prompts appear

Options:
  (none)

Example:
  ./notesctl permissions
HELP
}

cmd_permissions() {
  cat <<'TXT'
Permissions Guide (manual)
1) System Settings -> Privacy & Security -> Full Disk Access -> allow Terminal/iTerm
2) System Settings -> Privacy & Security -> Automation -> allow Terminal to control Notes
3) If prompts appear on first run, always click Allow
TXT
}

cmd_clean_cache_help() {
  cat <<'HELP'
Clean cache = maintainer-only repo-local cleanup.
Maintainer-only cleanup lane.

Usage:
  ./notesctl clean-cache --dry-run
  ./notesctl clean-cache [--apply]

Use this when:
  - you want to reclaim local rebuildable support surfaces
  - you want to preview cleanup before deleting anything
  - you want to reset repo-local tooling state without touching exported snapshots

Safety boundary:
  - only removes repo-local rebuildables and disposable-generated files
  - repo-local caches live under .runtime-cache/ whenever the repo owns them
  - never deletes exported snapshots under NOTES_SNAPSHOT_ROOT_DIR

Options:
  --dry-run            preview the current cleanup set without deleting it
  --apply              delete the current cleanup set (default)

Recommended next steps after cleanup:
  ./notesctl rebuild-dev-env
  ./notesctl status --full
  ./notesctl verify
  ./notesctl doctor

Examples:
  ./notesctl clean-cache --dry-run
  ./notesctl clean-cache
HELP
}

cmd_runtime_audit_help() {
  cat <<'HELP'
Runtime audit = inspect repo-local and external repo-owned runtime residue.

Use this when:
  - you want the current repo-local support surfaces and external cache roots listed together
  - you want a machine-readable report before touching launchd/runtime/browser residue
  - you want the conditional vendor-runtime path surfaced with the same TTL/budget contract

What it inspects:
  - repo-local: .runtime-cache/dev/venv, .runtime-cache/cache/apple-notes-snapshot, .runtime-cache/temp, .runtime-cache/logs, .runtime-cache/pytest, .runtime-cache/coverage, .runtime-cache/pycache
  - external repo-owned cleanup scope: current machine-cache entries for launchd, runtime, repo copies, and disposable browser temp state
  - persistent browser root: the repo-managed isolated Chrome root (reported, protected, excluded from TTL/cap cleanup)
  - conditional cache path: the vendor-runtime current pointer inside the repo-managed machine cache root
  - legacy migration roots from older Application Support and cache layouts

Safety boundary:
  - audit only; no deletions
  - does not scan system temp roots, Docker, or shared tool caches

Options:
  --json                   machine-readable report
  --retention-hours N      stale threshold for action hints (default: 72)
  --browser-retention-hours N
                           stale threshold for browser clone residue (default: 24)
  --max-external-bytes N   external cache budget before cleanup is recommended
  --include-vendor-runtime mark vendor-runtime/current as cleanup-eligible in the report

Examples:
  ./notesctl runtime-audit
  ./notesctl runtime-audit --json
HELP
}

cmd_clean_runtime_help() {
  cat <<'HELP'
Clean runtime = maintainer-only external repo-owned cleanup.

Usage:
  ./notesctl clean-runtime --dry-run
  ./notesctl clean-runtime [--apply] [--retention-hours N] [--browser-retention-hours N] [--max-external-bytes N] [--include-vendor-runtime]

Use this when:
  - clean-cache already reset repo-local tooling state, but external repo-owned runtime/cache residue still exists
  - you want stale non-current launchd/runtime/repo-copy/browser residue pruned safely
  - you want an explicit dry-run before deleting anything outside the repo root

Default deletion boundary:
  - stale non-current entries under the repo-managed machine cache root for launchd, runtime, repo copies, and disposable browser temp state
  - stale legacy entries under the old Application Support / ApplicationSupport roots during migration
  - the repo-managed isolated browser root is always protected and excluded from TTL/cap cleanup
  - current NOTES_SNAPSHOT_LAUNCHD_LABEL and NOTES_SNAPSHOT_LAUNCHD_WEB_LABEL are always protected
  - vendor-runtime/current stays opt-in for explicit cleanup via --include-vendor-runtime
  - the automatic janitor may still include vendor-runtime/current under the repo-owned TTL/budget contract
  - over-budget external cache entries may also become cleanup-eligible even if they are not stale

Out of scope:
  - repo-local caches (.runtime-cache/*) -> use ./notesctl clean-cache
  - system temp roots
  - Docker / clean-room / runner-temp / shared tool caches

Options:
  --dry-run                   preview the current cleanup set without deleting it
  --apply                     delete the current cleanup set (default)
  --retention-hours N         stale threshold in hours (default: 72)
  --browser-retention-hours N stale threshold for browser clone residue (default: 24)
  --max-external-bytes N      external cache budget before budget-based cleanup kicks in
  --include-vendor-runtime    allow vendor-runtime/current to be removed

Examples:
  ./notesctl clean-runtime --dry-run
  ./notesctl clean-runtime --dry-run --include-vendor-runtime
  ./notesctl clean-runtime
HELP
}

cmd_browser_contract_help() {
  cat <<'HELP'
Browser contract = resolve the isolated-root + single-instance + CDP attach-first contract for repo-owned browser automation.

Use this when:
  - you want the canonical isolated-root + single-instance + CDP attach contract
  - you want a fail-fast check instead of silently falling back to bundled Chromium or a second launch

Current contract:
  - NOTES_SNAPSHOT_BROWSER_PROVIDER must stay "chrome"
  - NOTES_SNAPSHOT_BROWSER_ROOT owns the repo-isolated browser lane
  - NOTES_SNAPSHOT_CHROME_USER_DATA_DIR points at the isolated Chrome user-data root
  - NOTES_SNAPSHOT_CHROME_PROFILE_NAME defaults to apple-notes-snapshot
  - NOTES_SNAPSHOT_CHROME_PROFILE_DIR defaults to Profile 1
  - NOTES_SNAPSHOT_CHROME_CDP_HOST/PORT define the attach endpoint for the single repo-owned Chrome instance
  - missing env or a missing profile is a fail-fast error
  - repo-owned browser automation does not silently fall back to Playwright bundled Chromium
  - browser/chrome-user-data is persistent and excluded from janitor TTL/cap cleanup
  - browser/tmp is the only disposable browser subtree

Examples:
  ./notesctl browser-contract
  ./notesctl browser-contract --json
HELP
}

cmd_browser_bootstrap_help() {
  cat <<'HELP'
Browser bootstrap = create the isolated repo-owned Chrome root from the default Chrome root.

Use this when:
  - the default Chrome root still holds the source profile you want to migrate
  - you want a one-time copy into the repo-managed isolated browser root
  - you want the target root normalized to Profile 1 plus a rewritten Local State

Bootstrap rules:
  - the default Chrome root must be quiet before copying
  - only Local State and the resolved source Profile directory are copied
  - Singleton*/DevToolsActivePort lock files are removed from the target
  - the target root is not overwritten if it already contains data
  - treat this as a one-time migration step, not a routine sync command
  - after you add or refresh logins inside the isolated root, do not rerun bootstrap unless you intentionally want to replace that isolated root from the default Chrome root

Examples:
  ./notesctl browser-bootstrap
  ./notesctl browser-bootstrap --json
HELP
}

cmd_browser_open_help() {
  cat <<'HELP'
Browser open = launch or attach to the single repo-owned Chrome instance.

Use this when:
  - you want to start the isolated Chrome instance if it is not running yet
  - you want the attach endpoint for Playwright/CDP clients when it is already running
  - you want to avoid second-launching the repo-owned Chrome root

Current behavior:
  - launches real Chrome with the isolated user-data dir, fixed profile dir, and CDP host/port
  - returns attach info instead of launching a second instance if the repo-owned instance is already running
  - fails fast if another Chrome instance already owns the configured CDP port
  - if the default port is occupied on your machine, use NOTES_SNAPSHOT_CHROME_CDP_PORT deliberately before launching or attaching

Examples:
  ./notesctl browser-open
  NOTES_SNAPSHOT_CHROME_CDP_PORT=9347 ./notesctl browser-open
  ./notesctl browser-open --json
HELP
}

cmd_rebuild_dev_env_help() {
  cat <<'HELP'
Rebuild dev env = recreate the repo-owned maintainer virtual environment.

Use this when:
  - you just ran clean-cache
  - the checkout moved to a new path
  - maintainer verification commands no longer match the current checkout

This is a maintainer lane, not a first-run requirement for the first successful snapshot.

Example:
  ./notesctl rebuild-dev-env
HELP
}

cmd_runtime_audit() {
  load_env_with_defaults
  ensure_lib_state
  local audit_script="${REPO_ROOT}/scripts/ops/runtime_audit.py"
  local py
  py="$(state_find_python)" || die "python3/python not found; required for runtime-audit"
  if [[ -z "$py" ]]; then
    die "python3/python not found; required for runtime-audit"
  fi
  require_file "$audit_script"
  "$py" "$audit_script" \
    --retention-hours "${NOTES_SNAPSHOT_EXTERNAL_CACHE_TTL_HOURS}" \
    --browser-retention-hours "${NOTES_SNAPSHOT_BROWSER_CLONE_TTL_HOURS}" \
    --max-external-bytes "${NOTES_SNAPSHOT_EXTERNAL_CACHE_MAX_BYTES}" \
    --repo-root "${REPO_ROOT}" \
    --launchd-root "$(launchd_bridge_root)" \
    --runtime-root "$(launchd_runtime_root)" \
    --repos-root "$(launchd_repos_root)" \
    --legacy-launchd-root "$(launchd_legacy_launchd_root)" \
    --legacy-runtime-root "$(launchd_legacy_runtime_root)" \
    --legacy-repos-root "$(launchd_legacy_repos_root)" \
    --vendor-runtime-root "$(launchd_vendor_runtime_root)" \
    --legacy-vendor-runtime-root "$(launchd_legacy_vendor_runtime_root)" \
    --browser-root "$(launchd_browser_root)" \
    --browser-user-data-root "$(launchd_browser_user_data_root)" \
    --browser-temp-root "$(launchd_browser_temp_root)" \
    --current-label "${NOTES_SNAPSHOT_LAUNCHD_LABEL}" \
    --current-label "${NOTES_SNAPSHOT_LAUNCHD_WEB_LABEL}" \
    "$@"

  # runtime-audit is also a janitor trigger, but it should report the current
  # residue first and then let the silent cleanup pass run afterward.
  run_external_cache_janitor
}

cmd_clean_runtime() {
  load_env_with_defaults
  ensure_lib_state
  local clean_script="${REPO_ROOT}/scripts/ops/clean_runtime.py"
  local py
  py="$(state_find_python)" || die "python3/python not found; required for clean-runtime"
  if [[ -z "$py" ]]; then
    die "python3/python not found; required for clean-runtime"
  fi
  require_file "$clean_script"
  "$py" "$clean_script" \
    --retention-hours "${NOTES_SNAPSHOT_EXTERNAL_CACHE_TTL_HOURS}" \
    --browser-retention-hours "${NOTES_SNAPSHOT_BROWSER_CLONE_TTL_HOURS}" \
    --max-external-bytes "${NOTES_SNAPSHOT_EXTERNAL_CACHE_MAX_BYTES}" \
    --repo-root "${REPO_ROOT}" \
    --launchd-root "$(launchd_bridge_root)" \
    --runtime-root "$(launchd_runtime_root)" \
    --repos-root "$(launchd_repos_root)" \
    --legacy-launchd-root "$(launchd_legacy_launchd_root)" \
    --legacy-runtime-root "$(launchd_legacy_runtime_root)" \
    --legacy-repos-root "$(launchd_legacy_repos_root)" \
    --vendor-runtime-root "$(launchd_vendor_runtime_root)" \
    --legacy-vendor-runtime-root "$(launchd_legacy_vendor_runtime_root)" \
    --browser-root "$(launchd_browser_root)" \
    --browser-user-data-root "$(launchd_browser_user_data_root)" \
    --browser-temp-root "$(launchd_browser_temp_root)" \
    --current-label "${NOTES_SNAPSHOT_LAUNCHD_LABEL}" \
    --current-label "${NOTES_SNAPSHOT_LAUNCHD_WEB_LABEL}" \
    "$@"
}

cmd_browser_contract() {
  load_env_with_defaults
  ensure_lib_state
  local browser_script="${REPO_ROOT}/scripts/ops/browser_contract.py"
  local py
  py="$(state_find_python)" || die "python3/python not found; required for browser-contract"
  if [[ -z "$py" ]]; then
    die "python3/python not found; required for browser-contract"
  fi
  require_file "$browser_script"
  "$py" "$browser_script" "$@"
}

cmd_browser_bootstrap() {
  load_env_with_defaults
  ensure_lib_state
  local bootstrap_script="${REPO_ROOT}/scripts/ops/browser_bootstrap.py"
  local py
  py="$(state_find_python)" || die "python3/python not found; required for browser-bootstrap"
  if [[ -z "$py" ]]; then
    die "python3/python not found; required for browser-bootstrap"
  fi
  require_file "$bootstrap_script"
  "$py" "$bootstrap_script" "$@"
}

cmd_browser_open() {
  load_env_with_defaults
  run_repo_local_cache_janitor
  run_external_cache_janitor
  ensure_lib_state
  local open_script="${REPO_ROOT}/scripts/ops/browser_open.py"
  local py
  py="$(state_find_python)" || die "python3/python not found; required for browser-open"
  if [[ -z "$py" ]]; then
    die "python3/python not found; required for browser-open"
  fi
  require_file "$open_script"
  "$py" "$open_script" "$@"
}

cmd_verify_help() {
  cat <<'HELP'
Verify = check whether the last successful snapshot is still fresh.

Use this after:
  - your first manual snapshot
  - scheduler installation
  - any troubleshooting or self-heal run

Current behavior:
  - exits 0 when the last success is fresh
  - exits 1 when the last success is stale
  - exits 2 when no successful run has been recorded yet

Options:
  (none)

Fail-fast note:
  If this prints "FAIL: no last_success record; run ./notesctl run",
  you have not completed the first successful snapshot yet.

Example:
  ./notesctl verify
HELP
}

cmd_verify() {
  run_zsh "$VERIFY_SCRIPT" "$@"
}

cmd_doctor_help() {
  cat <<'HELP'
Doctor = run the full local sanity check.

Use this when:
  - the first run did not behave as expected
  - launchd looks missing or stale
  - status looks confusing and you want the same config / launchd / ledger story in a troubleshooting view
  - you want a machine-readable dependency and warning report

Options:
  --json               machine-readable doctor output

Examples:
  ./notesctl doctor
  ./notesctl doctor --json
HELP
}

cmd_doctor() {
  run_zsh "$DOCTOR_SCRIPT" "$@"
}

cmd_audit_help() {
  cat <<'HELP'
Audit = inspect the local Web surface security contract.

Use this when:
  - you want the token, scope, allowlist, readonly, and rate-limit settings summarized
  - a Web action looks blocked and you want the contract before changing config
  - you are reviewing the Local Web API exposure before widening the bind address

Options:
  --json               machine-readable audit output

Examples:
  ./notesctl audit
  ./notesctl audit --json
HELP
}

cmd_audit() {
  load_env_with_defaults

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

  local -a failures warnings recs

  if [[ "${NOTES_SNAPSHOT_WEB_ENABLE}" == "1" ]]; then
    if [[ "${NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN}" == "1" && -z "${NOTES_SNAPSHOT_WEB_TOKEN}" ]]; then
      failures+=("token_required_missing")
      recs+=("Set NOTES_SNAPSHOT_WEB_TOKEN to a long random string.")
    fi
    if [[ "${NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN_FOR_STATIC}" == "1" && -z "${NOTES_SNAPSHOT_WEB_TOKEN}" ]]; then
      failures+=("static_token_required_missing")
      recs+=("Set NOTES_SNAPSHOT_WEB_TOKEN before enabling REQUIRE_TOKEN_FOR_STATIC.")
    fi
    if [[ "${NOTES_SNAPSHOT_WEB_ALLOW_REMOTE}" == "1" ]]; then
      if [[ "${NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN}" != "1" ]]; then
        failures+=("remote_without_token")
        recs+=("Set NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN=1 when allowing remote bind.")
      fi
      if [[ -z "${NOTES_SNAPSHOT_WEB_ALLOW_IPS}" ]]; then
        warnings+=("remote_without_allowlist")
        recs+=("Set NOTES_SNAPSHOT_WEB_ALLOW_IPS to restrict clients.")
      fi
    fi
    if [[ -z "${NOTES_SNAPSHOT_WEB_TOKEN_SCOPES}" || "${NOTES_SNAPSHOT_WEB_TOKEN_SCOPES:l}" == "all" ]]; then
      warnings+=("token_scopes_broad")
      recs+=("Prefer minimal scopes, e.g. NOTES_SNAPSHOT_WEB_TOKEN_SCOPES=read,run.")
    fi
    if [[ -z "${NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW}" || "${NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW:l}" == "all" ]]; then
      warnings+=("actions_allowlist_broad")
      recs+=("Prefer minimal allowlist, e.g. NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW=run.")
    fi
  fi

  if [[ "${NOTES_SNAPSHOT_WEB_ENABLE}" == "1" && -n "${NOTES_SNAPSHOT_WEB_TOKEN_SCOPES}" && "${NOTES_SNAPSHOT_WEB_TOKEN_SCOPES:l}" != "all" ]] \
    && [[ -n "${NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW}" && "${NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW:l}" != "all" ]]; then
    local -a scopes actions mismatched
    local scopes_csv=","
    IFS=',' read -r -A scopes <<< "${NOTES_SNAPSHOT_WEB_TOKEN_SCOPES}"
    for scope in "${scopes[@]}"; do
      scope="$(printf '%s' "$scope" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')"
      if [[ -n "$scope" ]]; then
        scopes_csv+="${scope},"
      fi
    done
    IFS=',' read -r -A actions <<< "${NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW}"
    for action in "${actions[@]}"; do
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
      failures+=("actions_not_covered_by_scopes:${mismatched[*]}")
      recs+=("Align NOTES_SNAPSHOT_WEB_TOKEN_SCOPES with actions allowlist.")
    fi
  fi

  if [[ "${NOTES_SNAPSHOT_WEB_ENABLE}" == "1" ]]; then
    if [[ "${NOTES_SNAPSHOT_WEB_RATE_LIMIT_MAX}" -le 0 || "${NOTES_SNAPSHOT_WEB_RATE_LIMIT_WINDOW_SEC}" -le 0 ]]; then
      warnings+=("rate_limit_disabled")
      recs+=("Enable API rate limiting with NOTES_SNAPSHOT_WEB_RATE_LIMIT_MAX and WINDOW_SEC.")
    fi
    if [[ -n "${NOTES_SNAPSHOT_WEB_ACTION_COOLDOWNS}" && "${NOTES_SNAPSHOT_WEB_ACTION_COOLDOWNS:l}" == "off" ]]; then
      warnings+=("action_cooldown_disabled")
      recs+=("Keep action cooldowns enabled to prevent rapid re-runs.")
    fi
  fi

  local level="OK"
  if [[ "${#failures[@]}" -gt 0 ]]; then
    level="FAIL"
  elif [[ "${#warnings[@]}" -gt 0 ]]; then
    level="WARN"
  fi

  if [[ "$output_json" -eq 0 ]]; then
    echo "Audit"
    echo "level=${level}"
    echo "require_token=${NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN}"
    echo "require_token_for_static=${NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN_FOR_STATIC}"
    echo "allow_remote=${NOTES_SNAPSHOT_WEB_ALLOW_REMOTE}"
    echo "allow_ips=${NOTES_SNAPSHOT_WEB_ALLOW_IPS:-}"
    echo "token_scopes=${NOTES_SNAPSHOT_WEB_TOKEN_SCOPES:-}"
    echo "actions_allow=${NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW:-}"
    echo "readonly=${NOTES_SNAPSHOT_WEB_READONLY}"
    echo "rate_limit_window_sec=${NOTES_SNAPSHOT_WEB_RATE_LIMIT_WINDOW_SEC}"
    echo "rate_limit_max=${NOTES_SNAPSHOT_WEB_RATE_LIMIT_MAX}"
    echo "action_cooldowns=${NOTES_SNAPSHOT_WEB_ACTION_COOLDOWNS:-}"
    if [[ "${#failures[@]}" -gt 0 ]]; then
      echo "Failures"
      for item in "${failures[@]}"; do
        echo "  - ${item}"
      done
    fi
    if [[ "${#warnings[@]}" -gt 0 ]]; then
      echo "Warnings"
      for item in "${warnings[@]}"; do
        echo "  - ${item}"
      done
    fi
    if [[ "${#recs[@]}" -gt 0 ]]; then
      echo "Fix Plan"
      for item in "${recs[@]}"; do
        echo "  - ${item}"
      done
    fi
    return 0
  fi

  json_escape() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    printf '%s' "$value"
  }

  local failures_json=""
  local warnings_json=""
  local recs_json=""
  if [[ "${#failures[@]}" -gt 0 ]]; then
    for item in "${failures[@]}"; do
      failures_json+="\"$(json_escape "$item")\","
    done
    failures_json="[${failures_json%,}]"
  else
    failures_json="[]"
  fi
  if [[ "${#warnings[@]}" -gt 0 ]]; then
    for item in "${warnings[@]}"; do
      warnings_json+="\"$(json_escape "$item")\","
    done
    warnings_json="[${warnings_json%,}]"
  else
    warnings_json="[]"
  fi
  if [[ "${#recs[@]}" -gt 0 ]]; then
    for item in "${recs[@]}"; do
      recs_json+="\"$(json_escape "$item")\","
    done
    recs_json="[${recs_json%,}]"
  else
    recs_json="[]"
  fi

  cat <<JSON
{
  "level": "$(json_escape "$level")",
  "config": {
    "require_token": "$(json_escape "$NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN")",
    "require_token_for_static": "$(json_escape "$NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN_FOR_STATIC")",
    "allow_remote": "$(json_escape "$NOTES_SNAPSHOT_WEB_ALLOW_REMOTE")",
    "allow_ips": "$(json_escape "${NOTES_SNAPSHOT_WEB_ALLOW_IPS:-}")",
    "token_scopes": "$(json_escape "${NOTES_SNAPSHOT_WEB_TOKEN_SCOPES:-}")",
    "actions_allow": "$(json_escape "${NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW:-}")",
    "readonly": "$(json_escape "$NOTES_SNAPSHOT_WEB_READONLY")",
    "rate_limit_window_sec": "$(json_escape "$NOTES_SNAPSHOT_WEB_RATE_LIMIT_WINDOW_SEC")",
    "rate_limit_max": "$(json_escape "$NOTES_SNAPSHOT_WEB_RATE_LIMIT_MAX")",
    "action_cooldowns": "$(json_escape "${NOTES_SNAPSHOT_WEB_ACTION_COOLDOWNS:-}")"
  },
  "failures": ${failures_json},
  "warnings": ${warnings_json},
  "recommendations": ${recs_json}
}
JSON
}

cmd_logs() {
  run_zsh "$LOGS_SCRIPT" "$@"
}

cmd_dashboard() {
  ensure_lib_state
  local dashboard_script="${REPO_ROOT}/scripts/ops/dashboard_notes_snapshot.py"
  local py
  py="$(state_find_python)" || die "python3/python not found; required for dashboard"
  if [[ -z "$py" ]]; then
    die "python3/python not found; required for dashboard"
  fi
  require_file "$dashboard_script"
  "$py" "$dashboard_script"
}

cmd_aggregate() {
  load_env_with_defaults
  ensure_lib_state
  local aggregate_script="${REPO_ROOT}/scripts/ops/aggregate_runs.py"
  local py
  py="$(state_find_python)" || die "python3/python not found; required for aggregate"
  if [[ -z "$py" ]]; then
    die "python3/python not found; required for aggregate"
  fi
  require_file "$aggregate_script"
  "$py" "$aggregate_script" "$@"
}

cmd_ai_diagnose_help() {
  cat <<'HELP'
AI Diagnose = opt-in advisory diagnosis for the current local backup state.

What it reads:
  - ./notesctl status --json
  - ./notesctl doctor --json
  - ./notesctl log-health --json
  - ./notesctl aggregate --tail <n>

What it does not read in v1:
  - exported note content
  - Apple Notes bodies
  - any remote control-plane state

Safety model:
  - advisory only; never the canonical system truth
  - routes model calls through a local Switchyard runtime when AI is enabled
  - does not change run/install/verify hot paths
  - degrades to a deterministic summary when AI is disabled or misconfigured

Options:
  --json               machine-readable report
  --provider <name>    override configured provider for this run
  --model <name>       override configured model for this run
  --tail <count>       recent runs to include from aggregate summary (default: 5)

Examples:
  ./notesctl ai-diagnose
  ./notesctl ai-diagnose --json
  ./notesctl ai-diagnose --provider gemini --model gemini-2.5-flash
HELP
}

cmd_ai_diagnose() {
  load_env_with_defaults
  ensure_lib_state
  local diagnose_script="${REPO_ROOT}/scripts/ops/ai_diagnose.py"
  local py
  py="$(state_find_python)" || die "python3/python not found; required for ai-diagnose"
  if [[ -z "$py" ]]; then
    die "python3/python not found; required for ai-diagnose"
  fi
  require_file "$diagnose_script"
  "$py" "$diagnose_script" "$@"
}

cmd_mcp_help() {
  cat <<'HELP'
MCP = stdio-first, read-only-first agent-facing surface for Apple Notes Snapshot.

Use this when:
  - you want an MCP host or client to inspect the local backup state
  - you want tools/resources backed by notesctl, state.json, and run summaries
  - you do not want to expose the local Web console as a remote agent surface

Current v1 scope:
  - stdio transport only
  - read-only tools and resources only
  - no note-content access
  - no high-side-effect write tools

Examples:
  ./notesctl mcp
HELP
}

cmd_mcp() {
  load_env_with_defaults
  ensure_lib_state
  local mcp_script="${REPO_ROOT}/scripts/mcp/server.py"
  local py
  py="$(state_find_python)" || die "python3/python not found; required for mcp"
  if [[ -z "$py" ]]; then
    die "python3/python not found; required for mcp"
  fi
  require_file "$mcp_script"
  "$py" "$mcp_script" "$@"
}

cmd_web_help() {
  cat <<'HELP'
Web = token-gated local browser control room plus same-machine Local Web API.

Use this when:
  - you want the browser dashboard for status, health, doctor, recent runs, and access policy
  - you want a same-machine JSON API for local tooling or browser-backed workflows
  - you do not want to pretend this is a public OpenAPI or hosted API surface

Read endpoints:
  - /api/health
  - /api/status
  - /api/log-health?tail=<n>
  - /api/doctor
  - /api/metrics?tail=<n>
  - /api/recent-runs?tail=<n>
  - /api/access

Safety model:
  - token-gated by default when NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN=1
  - same-machine fit first; keep 127.0.0.1 unless you have a deliberate local-network reason
  - reuses the same repo-owned notesctl/status/doctor/aggregate surfaces
  - does not become a public OpenAPI, generated SDK, or hosted control plane

Examples:
  export NOTES_SNAPSHOT_WEB_TOKEN="a-long-random-token"
  ./notesctl web --host 127.0.0.1 --port 8080
HELP
}

cmd_web() {
  load_env_with_defaults
  run_repo_local_cache_janitor
  run_external_cache_janitor
  ensure_lib_state
  local web_script="${REPO_ROOT}/scripts/ops/web_server.py"
  local py
  py="$(state_find_python)" || die "python3/python not found; required for web"
  if [[ -z "$py" ]]; then
    die "python3/python not found; required for web"
  fi
  if [[ "${NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN}" == "1" ]] && [[ -z "${NOTES_SNAPSHOT_WEB_TOKEN}" ]]; then
    die "NOTES_SNAPSHOT_WEB_TOKEN is required when NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN=1"
  fi
  if [[ "${NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN_FOR_STATIC}" == "1" ]] && [[ -z "${NOTES_SNAPSHOT_WEB_TOKEN}" ]]; then
    die "NOTES_SNAPSHOT_WEB_TOKEN is required when NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN_FOR_STATIC=1"
  fi
  require_file "$web_script"
  "$py" "$web_script" "$@"
}

cmd_log_health() {
  load_env_with_defaults

  ensure_lib_state
  state_set_paths "$NOTES_SNAPSHOT_STATE_DIR"

  local tail_lines="$NOTES_SNAPSHOT_TAIL_LINES"
  local output_json=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --tail)
        tail_lines="$2"
        shift 2
        ;;
      --json)
        output_json=1
        shift
        ;;
      *)
        die "unknown arg: $1"
        ;;
    esac
  done

  if [[ ! "$tail_lines" =~ ^[0-9]+$ ]] || [[ "$tail_lines" -le 0 ]]; then
    die "invalid --tail: $tail_lines"
  fi

  local stderr_log="${NOTES_SNAPSHOT_LOG_DIR}/stderr.log"
  local launchd_err="${NOTES_SNAPSHOT_LOG_DIR}/launchd.err.log"
  local stdout_log="${NOTES_SNAPSHOT_LOG_DIR}/stdout.log"
  local pattern="${NOTES_SNAPSHOT_LOG_HEALTH_PATTERN}"

  local err_stdout=0
  local err_stderr=0
  local err_launchd=0
  read -r err_stdout err_stderr err_launchd < <(log_health_counts "$NOTES_SNAPSHOT_LOG_DIR" "$tail_lines" "$pattern")

  local total_err=$(( err_stderr + err_launchd + err_stdout ))

  local last_success_epoch=""
  local last_success_iso=""

  state_load_state_prefer_json "$STATE_FILE" "$LAST_RUN_FILE" "$LAST_SUCCESS_FILE" "$STATE_JSON_FILE"
  local state_status="${STATE_STATUS:-unknown}"

  local health="OK"
  if [[ "$state_status" != "success" ]]; then
    health="FAIL"
  fi
  if [[ "$total_err" -ge 5 ]]; then
    health="FAIL"
  elif [[ "$total_err" -gt 0 ]] && [[ "$health" != "FAIL" ]]; then
    health="WARN"
  fi

  local age_sec=""
  if [[ -n "${last_success_epoch:-}" ]]; then
    age_sec=$(( $(date +%s) - last_success_epoch ))
    if [[ "$age_sec" -gt "$NOTES_SNAPSHOT_STALE_THRESHOLD_SEC" ]] && [[ "$health" != "FAIL" ]]; then
      health="WARN"
    fi
  else
    if [[ "$health" == "OK" ]]; then
      health="WARN"
    fi
  fi

  if [[ "$output_json" -eq 0 ]]; then
    echo "Log Health"
    echo "health=${health}"
    echo "pattern=${pattern}"
    echo "tail_lines=${tail_lines}"
    echo "errors_stdout=${err_stdout}"
    echo "errors_stderr=${err_stderr}"
    echo "errors_launchd_err=${err_launchd}"
    echo "errors_total=${total_err}"
    echo "last_status=${state_status}"
    if [[ -n "${last_success_iso:-}" ]]; then
      echo "last_success_iso=${last_success_iso}"
    fi
    if [[ -n "$age_sec" ]]; then
      echo "last_success_age_sec=${age_sec}"
    fi
  fi

  if [[ "$health" == "FAIL" ]]; then
    if [[ "$output_json" -eq 0 ]]; then
      echo "NEXT: ./notesctl self-heal"
    fi
  elif [[ "$health" == "WARN" ]]; then
    if [[ "$output_json" -eq 0 ]]; then
      echo "NEXT: ./notesctl status --verbose --tail ${tail_lines}"
    fi
  else
    if [[ "$output_json" -eq 0 ]]; then
      echo "NEXT: no action needed"
    fi
  fi

  if [[ "$output_json" -eq 1 ]]; then
    json_escape() {
      local value="$1"
      value="${value//\\/\\\\}"
      value="${value//\"/\\\"}"
      printf '%s' "$value"
    }
    cat <<JSON
{
  "health": "$(json_escape "$health")",
  "pattern": "$(json_escape "$pattern")",
  "tail_lines": $tail_lines,
  "errors_stdout": $err_stdout,
  "errors_stderr": $err_stderr,
  "errors_launchd_err": $err_launchd,
  "errors_total": $total_err,
  "last_status": "$(json_escape "${status:-unknown}")",
  "last_success_iso": "$(json_escape "${last_success_iso:-}")",
  "last_success_age_sec": "${age_sec:-}"
}
JSON
  fi
}

cmd_rotate_logs() {
  run_zsh "$ROTATE_SCRIPT" "$@"
}

cmd_clean_cache() {
  run_zsh "$CLEAN_SCRIPT" "$@"
}

cmd_rebuild_dev_env() {
  load_env_with_defaults
  run_repo_local_cache_janitor
  run_external_cache_janitor
  local rebuild_script="${REPO_ROOT}/scripts/ops/rebuild_dev_env.zsh"
  require_file "$rebuild_script"
  run_zsh "$rebuild_script" "$@"
}

cmd_run_help() {
  cat <<'HELP'
Run = trigger one snapshot now.

This is step 2 of the public first-successful-run path:
  1. review config/notes_snapshot.env
  2. ./notesctl run --no-status
  3. ./notesctl install --minutes 30 --load
  4. ./notesctl verify
     ./notesctl doctor

Most people should treat this as a 3-step, about-3-minute setup path,
not a one-minute instant demo. The first run may trigger Apple Notes /
AppleScript permission prompts.

Options:
  --no-status          skip the follow-up status report
  --brief              show brief status after the run
  --full               show full status after the run
  --verbose            show verbose status after the run

Examples:
  ./notesctl run --no-status
  ./notesctl run --brief
HELP
}

cmd_run() {
  load_env_with_defaults
  run_repo_local_cache_janitor
  run_external_cache_janitor
  local no_status=0
  local mode="brief"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --no-status)
        no_status=1
        shift
        ;;
      --brief)
        mode="brief"
        shift
        ;;
      --full)
        mode="full"
        shift
        ;;
      --verbose)
        mode="verbose"
        shift
        ;;
      *)
        die "unknown arg: $1"
        ;;
    esac
  done

  run_zsh "$WRAPPER_SCRIPT"

  if [[ "$no_status" -eq 0 ]] && [[ -f "$STATUS_SCRIPT" ]]; then
    run_zsh "$STATUS_SCRIPT" "--${mode}"
  fi
}
