#!/bin/zsh

# ------------------------------
# Shared helpers (sourced)
# ------------------------------
line() { printf '%s\n' "----------------------------------------"; }
info() { printf 'INFO: %s\n' "$1"; }
warn() { printf 'WARN: %s\n' "$1" >&2; }
die() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }

# ------------------------------
# PATH baseline
# ------------------------------
ensure_path() {
  local default_path="/usr/bin:/bin:/usr/sbin:/sbin"
  if [[ -z "${PATH:-}" ]]; then
    export PATH="$default_path"
    return 0
  fi
  if ! command -v date >/dev/null 2>&1; then
    PATH="${PATH}:${default_path}"
  fi
}

ensure_path

# ------------------------------
# Command paths
# ------------------------------
resolve_bin() {
  local name="$1"
  local preferred="$2"
  if [[ -n "$preferred" && -x "$preferred" ]]; then
    printf '%s' "$preferred"
    return 0
  fi
  local found=""
  found="$(command -v "$name" 2>/dev/null || true)"
  if [[ -n "$found" ]]; then
    printf '%s' "$found"
    return 0
  fi
  return 1
}

MKDIR_BIN="$(resolve_bin mkdir /bin/mkdir)" || die "missing executable: mkdir"
RMDIR_BIN="$(resolve_bin rmdir /bin/rmdir)" || die "missing executable: rmdir"
DATE_BIN="$(resolve_bin date /bin/date)" || die "missing executable: date"
MV_BIN="$(resolve_bin mv /bin/mv)" || die "missing executable: mv"
CP_BIN="$(resolve_bin cp /bin/cp)" || die "missing executable: cp"
RM_BIN="$(resolve_bin rm /bin/rm)" || die "missing executable: rm"
WC_BIN="$(resolve_bin wc /usr/bin/wc)" || die "missing executable: wc"
TR_BIN="$(resolve_bin tr /usr/bin/tr)" || die "missing executable: tr"
TAIL_BIN="$(resolve_bin tail /usr/bin/tail)" || die "missing executable: tail"
GREP_BIN="$(resolve_bin grep /usr/bin/grep)" || die "missing executable: grep"
STAT_BIN="$(resolve_bin stat /usr/bin/stat)" || die "missing executable: stat"
PS_BIN="$(resolve_bin ps /bin/ps)" || die "missing executable: ps"
MKTEMP_BIN="$(resolve_bin mktemp /usr/bin/mktemp)" || die "missing executable: mktemp"
CAT_BIN="$(resolve_bin cat /bin/cat)" || die "missing executable: cat"
AWK_BIN="$(resolve_bin awk /usr/bin/awk)" || die "missing executable: awk"
SED_BIN="$(resolve_bin sed /usr/bin/sed)" || die "missing executable: sed"
CUT_BIN="$(resolve_bin cut /usr/bin/cut)" || die "missing executable: cut"
SORT_BIN="$(resolve_bin sort /usr/bin/sort)" || die "missing executable: sort"
UNIQ_BIN="$(resolve_bin uniq /usr/bin/uniq)" || die "missing executable: uniq"
HEAD_BIN="$(resolve_bin head /usr/bin/head)" || die "missing executable: head"
ID_BIN="$(resolve_bin id /usr/bin/id)" || die "missing executable: id"

# ------------------------------
# Command shims
# ------------------------------
date() { "$DATE_BIN" "$@"; }
mv() { "$MV_BIN" "$@"; }
cp() { "$CP_BIN" "$@"; }
rm() { "$RM_BIN" "$@"; }
wc() { "$WC_BIN" "$@"; }
tr() { "$TR_BIN" "$@"; }
tail() { "$TAIL_BIN" "$@"; }
grep() { "$GREP_BIN" "$@"; }
stat() { "$STAT_BIN" "$@"; }
ps() { "$PS_BIN" "$@"; }
mktemp() { "$MKTEMP_BIN" "$@"; }
mkdir() { "$MKDIR_BIN" "$@"; }
rmdir() { "$RMDIR_BIN" "$@"; }
cat() { "$CAT_BIN" "$@"; }
awk() { "$AWK_BIN" "$@"; }
sed() { "$SED_BIN" "$@"; }
cut() { "$CUT_BIN" "$@"; }
sort() { "$SORT_BIN" "$@"; }
uniq() { "$UNIQ_BIN" "$@"; }
head() { "$HEAD_BIN" "$@"; }
id() { "$ID_BIN" "$@"; }

load_env() {
  if [[ -f "${ENV_FILE:-}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi
}

validate_int() {
  local name="$1"
  local value="$2"
  if [[ ! "$value" =~ ^[0-9]+$ ]] || [[ "$value" -le 0 ]]; then
    die "invalid ${name}: ${value}"
  fi
}

validate_uint() {
  local name="$1"
  local value="$2"
  if [[ ! "$value" =~ ^[0-9]+$ ]]; then
    die "invalid ${name}: ${value}"
  fi
}

validate_path() {
  local value="$1"
  if [[ -z "$value" ]]; then
    die "path is empty"
  fi
  if [[ "$value" == *$'\n'* ]]; then
    die "path contains newline"
  fi
}

validate_abs_path() {
  local name="$1"
  local value="$2"
  validate_path "$value"
  if [[ "$value" != /* ]]; then
    die "path is not absolute: ${name}=${value}"
  fi
}

require_exec() {
  local path="$1"
  if [[ ! -x "$path" ]]; then
    die "missing executable: $path"
  fi
}

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    die "missing file: $path"
  fi
}

run_zsh() {
  local path="$1"
  shift
  require_file "$path"
  /bin/zsh "$path" "$@"
}

ensure_dir() {
  local dir="$1"
  if ! "$MKDIR_BIN" -p -- "$dir"; then
    die "failed to create dir: $dir"
  fi
}

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  printf '%s' "$value"
}

log_line() {
  local msg="$1"
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  printf '%s %s\n' "$ts" "$msg"

  if [[ "${NOTES_SNAPSHOT_LOG_JSONL:-0}" == "1" ]]; then
    if [[ -n "${NOTES_SNAPSHOT_LOG_DIR:-}" && -d "${NOTES_SNAPSHOT_LOG_DIR}" ]]; then
      local iso
      iso="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
      local json
      json="{\"ts\":\"$(json_escape "$iso")\",\"message\":\"$(json_escape "$msg")\""
      if [[ -n "${NOTES_SNAPSHOT_RUN_ID:-}" ]]; then
        json+=",\"run_id\":\"$(json_escape "$NOTES_SNAPSHOT_RUN_ID")\""
      fi
      if [[ -n "${NOTES_SNAPSHOT_TRIGGER_SOURCE:-}" ]]; then
        json+=",\"trigger_source\":\"$(json_escape "$NOTES_SNAPSHOT_TRIGGER_SOURCE")\""
      fi
      if [[ -n "${NOTES_SNAPSHOT_RUN_PID:-}" && "${NOTES_SNAPSHOT_RUN_PID}" =~ ^[0-9]+$ ]]; then
        json+=",\"pid\":${NOTES_SNAPSHOT_RUN_PID}"
      fi
      json+="}"
      printf '%s\n' "$json" >> "${NOTES_SNAPSHOT_LOG_DIR}/structured.jsonl"
    fi
  fi
}

rotate_log() {
  local file="$1"
  local max_bytes="$2"
  local backups="$3"
  local mode="$4"

  if [[ ! -f "$file" ]]; then
    return 0
  fi

  local size
  size=$(wc -c < "$file" | tr -d ' ')
  if [[ "$size" -lt "$max_bytes" ]]; then
    return 0
  fi

  local stale="${file}.$((backups + 1))"
  if [[ -f "$stale" ]]; then
    rm -f -- "$stale"
  fi

  local i
  for ((i=backups-1; i>=1; i--)); do
    local src="${file}.${i}"
    local dst="${file}.$((i+1))"
    if [[ -f "$src" ]]; then
      mv -f -- "$src" "$dst"
    fi
  done

  if [[ "$mode" == "copytruncate" ]]; then
    cp -f -- "$file" "${file}.1"
    : > "$file"
  else
    mv -f -- "$file" "${file}.1"
    : > "$file"
  fi
}

rotate_log_if_needed() {
  local file="$1"
  local max_bytes="$2"
  local backups="$3"
  local mode="$4"

  if [[ ! -f "$file" ]]; then
    return 1
  fi

  local size
  size=$(wc -c < "$file" | tr -d ' ')
  if [[ "$size" -lt "$max_bytes" ]]; then
    return 1
  fi

  rotate_log "$file" "$max_bytes" "$backups" "$mode"
  return 0
}

rotate_logs() {
  local max_bytes="$1"
  local backups="$2"
  local mode="$3"
  rotate_log "${NOTES_SNAPSHOT_LOG_DIR}/stdout.log" "$max_bytes" "$backups" "$mode"
  rotate_log "${NOTES_SNAPSHOT_LOG_DIR}/stderr.log" "$max_bytes" "$backups" "$mode"
  rotate_log "${NOTES_SNAPSHOT_LOG_DIR}/launchd.out.log" "$max_bytes" "$backups" "$mode"
  rotate_log "${NOTES_SNAPSHOT_LOG_DIR}/launchd.err.log" "$max_bytes" "$backups" "$mode"
  rotate_log "${NOTES_SNAPSHOT_LOG_DIR}/structured.jsonl" "$max_bytes" "$backups" "$mode"
}

rotate_files_summary() {
  local max_bytes="$1"
  local backups="$2"
  local mode="$3"
  shift 3

  local total=0
  local rotated=0
  local missing=0

  local file
  for file in "$@"; do
    total=$(( total + 1 ))
    if [[ ! -f "$file" ]]; then
      missing=$(( missing + 1 ))
      continue
    fi
    if rotate_log_if_needed "$file" "$max_bytes" "$backups" "$mode"; then
      rotated=$(( rotated + 1 ))
    fi
  done

  printf 'log rotation done (mode=%s max_bytes=%s backups=%s files=%s rotated=%s missing=%s)\n' \
    "$mode" "$max_bytes" "$backups" "$total" "$rotated" "$missing"
}

log_health_counts() {
  local log_dir="$1"
  local tail_lines="$2"
  local pattern="$3"

  local stderr_log="${log_dir}/stderr.log"
  local launchd_err="${log_dir}/launchd.err.log"
  local stdout_log="${log_dir}/stdout.log"

  local err_stdout=0
  local err_stderr=0
  local err_launchd=0

  if [[ -f "$stderr_log" ]]; then
    err_stderr=$(tail -n "$tail_lines" "$stderr_log" | grep -E -c "$pattern" || true)
  fi
  if [[ -f "$launchd_err" ]]; then
    err_launchd=$(tail -n "$tail_lines" "$launchd_err" | grep -E -c "$pattern" || true)
  fi
  if [[ -f "$stdout_log" ]]; then
    err_stdout=$(tail -n "$tail_lines" "$stdout_log" | grep -E -c "$pattern" || true)
  fi

  printf '%s %s %s\n' "$err_stdout" "$err_stderr" "$err_launchd"
}
