#!/bin/sh
set -eu

find_repo_root() {
  candidate="$1"
  if [ -z "$candidate" ]; then
    return 1
  fi

  while [ "$candidate" != "/" ]; do
    if [ -x "$candidate/notesctl" ] && [ -f "$candidate/config/notes_snapshot.env" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
    candidate=$(dirname "$candidate")
  done

  return 1
}

print_only=0
if [ "${1-}" = "--print-path" ]; then
  print_only=1
  shift
fi

repo_root=""

for raw_candidate in "${APPLE_NOTES_SNAPSHOT_REPO_ROOT-}" "${CLAUDE_PROJECT_DIR-}" "${CODEX_PROJECT_DIR-}" "${PWD-}"; do
  if repo_root=$(find_repo_root "$raw_candidate"); then
    break
  fi
done

if [ -z "$repo_root" ] && command -v git >/dev/null 2>&1; then
  git_root=$(git rev-parse --show-toplevel 2>/dev/null || true)
  if repo_root=$(find_repo_root "$git_root"); then
    :
  fi
fi

if [ -z "$repo_root" ]; then
  cat >&2 <<'EOF'
Apple Notes Snapshot plugin bundle could not find a repo root.
Set APPLE_NOTES_SNAPSHOT_REPO_ROOT to the checkout that contains ./notesctl,
or install the bundle from inside the apple-notes-snapshot project directory.
EOF
  exit 1
fi

notesctl_path="$repo_root/notesctl"

if [ "$print_only" -eq 1 ]; then
  printf '%s\n' "$notesctl_path"
  exit 0
fi

exec "$notesctl_path" mcp "$@"
