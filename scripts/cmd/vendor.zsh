#!/bin/zsh

# ------------------------------
# Vendor commands (sourced)
# ------------------------------
cmd_update_vendor() {
  if ! command -v git >/dev/null 2>&1; then
    die "git not found; install git first"
  fi

  load_env_with_defaults

  local requested_ref=""
  local patch_dry_run=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --ref)
        [[ $# -lt 2 ]] && die "--ref requires a value"
        requested_ref="$2"
        shift 2
        ;;
      --patch-dry-run)
        patch_dry_run=1
        shift
        ;;
      *)
        die "unknown arg: $1"
        ;;
    esac
  done

  if [[ -z "$requested_ref" ]] && [[ -n "$NOTES_SNAPSHOT_VENDOR_REF" ]]; then
    requested_ref="$NOTES_SNAPSHOT_VENDOR_REF"
  fi

  local vendor_dir="${REPO_ROOT}/vendor"
  local target_dir="${vendor_dir}/notes-exporter"
  local remote_url="${NOTES_SNAPSHOT_VENDOR_URL}"
  local patch_dir="${NOTES_SNAPSHOT_VENDOR_PATCH_DIR:-}"

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  cleanup_tmp() {
    rm -rf "$tmp_dir"
  }
  trap "rm -rf '${tmp_dir}'" EXIT

  if [[ -z "$remote_url" ]]; then
    die "NOTES_SNAPSHOT_VENDOR_URL is empty"
  fi

  validate_provenance_field() {
    local field_name="$1"
    local field_value="$2"
    if [[ -z "$field_value" ]] || [[ "$field_value" == "unknown" ]]; then
      die "vendor provenance incomplete: ${field_name}=${field_value:-<empty>}"
    fi
  }
  validate_provenance_field "source" "$remote_url"
  if [[ -n "$requested_ref" ]]; then
    validate_provenance_field "requested_ref" "$requested_ref"
  fi

  if [[ -z "$requested_ref" ]]; then
    git clone --depth 1 "$remote_url" "$tmp_dir/notes-exporter"
  else
    git clone --depth 1 "$remote_url" "$tmp_dir/notes-exporter"
    git -C "$tmp_dir/notes-exporter" fetch --depth 1 origin "$requested_ref"
    git -C "$tmp_dir/notes-exporter" checkout "$requested_ref"
  fi

  calc_patch_hash() {
    local -a files=("$@")
    if command -v shasum >/dev/null 2>&1; then
      shasum -a 256 "${files[@]}" | awk '{print $1}' | tr '\n' '' | shasum -a 256 | awk '{print $1}'
      return 0
    fi
    if command -v openssl >/dev/null 2>&1; then
      openssl dgst -sha256 "${files[@]}" | awk '{print $2}' | tr '\n' '' | openssl dgst -sha256 | awk '{print $2}'
      return 0
    fi
    return 1
  }

  if [[ -n "$patch_dir" ]] && [[ -d "$patch_dir" ]]; then
    info "patch overlay enabled: dir=$patch_dir"
    local patch
    local applied=0
    local skipped=0
    local -a patches=("${patch_dir}"/*.patch(N))
    local patch_hash=""
    local patch_list=""
    if [[ "${#patches[@]}" -gt 0 ]]; then
      patch_list="$(printf '%s,' "${patches[@]##*/}" | sed 's/,$//')"
      patch_hash="$(calc_patch_hash "${patches[@]}" || true)"
      if [[ -n "$patch_hash" ]]; then
        info "patch overlay hash: ${patch_hash}"
      fi
    fi
    for patch in "${patch_dir}"/*.patch(N); do
      if [[ ! -f "$patch" ]]; then
        continue
      fi
      info "apply vendor patch: $patch"
      if [[ "$patch_dry_run" -eq 1 ]]; then
        if git -C "$tmp_dir/notes-exporter" apply --check --whitespace=nowarn "$patch" >/dev/null 2>&1; then
          applied=1
          continue
        fi
        if git -C "$tmp_dir/notes-exporter" apply --reverse --check "$patch" >/dev/null 2>&1; then
          info "patch already applied: $patch"
          skipped=$(( skipped + 1 ))
          continue
        fi
        warn "patch failed; vendor unchanged"
        die "failed to apply patch: $patch"
      else
        if git -C "$tmp_dir/notes-exporter" apply --check --whitespace=nowarn "$patch" >/dev/null 2>&1; then
          git -C "$tmp_dir/notes-exporter" apply --whitespace=nowarn "$patch" || die "failed to apply patch: $patch"
          applied=1
          continue
        fi
        if git -C "$tmp_dir/notes-exporter" apply --reverse --check "$patch" >/dev/null 2>&1; then
          info "patch already applied: $patch"
          skipped=$(( skipped + 1 ))
          continue
        fi
        warn "patch failed; vendor unchanged"
        die "failed to apply patch: $patch"
      fi
    done
    if [[ "$applied" -eq 0 ]]; then
      info "vendor patch dir exists but no .patch files found"
    else
      info "patch overlay summary: applied=$applied skipped=$skipped"
    fi
    if [[ "$patch_dry_run" -eq 1 ]]; then
      info "patch dry-run complete; vendor unchanged"
      cleanup_tmp
      return 0
    fi
  fi

  local requested_ref_value="${requested_ref:-HEAD}"
  local commit_sha
  commit_sha="$(git -C "$tmp_dir/notes-exporter" rev-parse HEAD)"
  local patch_dir_record=""
  local source_only_filters="__pycache__,.pytest_cache,*.pyc,*.pyo,tests/test_results.txt"
  validate_provenance_field "requested_ref" "$requested_ref_value"
  validate_provenance_field "commit" "$commit_sha"

  if [[ -n "$patch_dir" ]] && [[ -d "$patch_dir" ]]; then
    if [[ "$patch_dir" == "${REPO_ROOT}"/* ]]; then
      patch_dir_record="${patch_dir#${REPO_ROOT}/}"
    else
      patch_dir_record="$patch_dir"
    fi
  fi

  "$MKDIR_BIN" -p -- "$vendor_dir"
  local stage_dir="${vendor_dir}/.notes-exporter.tmp.$$"
  rm -rf "$stage_dir"
  cp -R "$tmp_dir/notes-exporter" "$stage_dir" || die "failed to stage vendor contents"
  rm -rf "$stage_dir/.git"
  # Strip transient test/cached artifacts so the vendored tree stays source-only.
  find "$stage_dir" -type d \( -name '__pycache__' -o -name '.pytest_cache' \) -prune -exec rm -rf {} + 2>/dev/null || true
  find "$stage_dir" -type f \( -name '*.pyc' -o -name '*.pyo' \) -exec rm -f {} + 2>/dev/null || true
  rm -f "$stage_dir/tests/test_results.txt"

  cat <<INFO > "$stage_dir/VENDOR_INFO"
source = $remote_url
requested_ref = $requested_ref_value
ref = $requested_ref_value
resolved_commit = $commit_sha
commit = $commit_sha
updated_at = $(date '+%Y-%m-%dT%H:%M:%S%z')
patch_dir = ${patch_dir_record:-}
patch_list = ${patch_list:-}
patch_hash = ${patch_hash:-}
base_match_status = exact-upstream-ref-with-source-only-filter
source_only_filters = ${source_only_filters}
INFO

  chmod +x "$stage_dir/exportnotes.zsh"
  info "vendor update ready; replacing target"
  rm -rf "$target_dir"
  mv -f -- "$stage_dir" "$target_dir"
  cleanup_tmp
}

cmd_update_vendor_commit() {
  cmd_update_vendor "$@"

  if [[ ! -d "${REPO_ROOT}/.git" ]]; then
    die "not a git repo: $REPO_ROOT"
  fi

  local vendor_dir="${REPO_ROOT}/vendor/notes-exporter"
  local vendor_info="${vendor_dir}/VENDOR_INFO"

  if git diff --quiet -- "$vendor_dir" && [[ -z "$(git status --porcelain -- "$vendor_dir")" ]]; then
    info "no changes in vendor; skip commit"
    return 0
  fi

  git add "$vendor_dir"

  local file_count
  local stats
  local added
  local deleted
  local commit_sha

  file_count=$(git diff --cached --name-only -- "$vendor_dir" | wc -l | tr -d ' ')
  stats=$(git diff --cached --numstat -- "$vendor_dir")
  added=$(echo "$stats" | awk '{if ($1 ~ /^[0-9]+$/) add+=$1} END{print add+0}')
  deleted=$(echo "$stats" | awk '{if ($2 ~ /^[0-9]+$/) del+=$2} END{print del+0}')

  commit_sha=""
  if [[ -f "$vendor_info" ]]; then
    commit_sha=$(awk -F ' = ' '/^commit =/ {print $2}' "$vendor_info")
  fi

  cat <<EOM | git commit -F -
chore(vendor): update vendored notes-exporter

## Summary
Keep vendored notes-exporter aligned with upstream to ensure deterministic snapshots.

## Key Changes
### Vendor
- refresh vendor/notes-exporter${commit_sha:+ to $commit_sha}
- update VENDOR_INFO metadata

## Tech Debt (if any)
- [ ] none

## Scope
- vendor refresh only

Files changed: ${file_count} (+${added}/-${deleted})
EOM
}
