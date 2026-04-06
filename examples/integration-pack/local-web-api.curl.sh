#!/usr/bin/env bash
set -euo pipefail

: "${NOTES_SNAPSHOT_WEB_TOKEN:?set NOTES_SNAPSHOT_WEB_TOKEN first}"

BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"

curl -H "Authorization: Bearer ${NOTES_SNAPSHOT_WEB_TOKEN}" \
  "${BASE_URL}/api/status"

curl -H "Authorization: Bearer ${NOTES_SNAPSHOT_WEB_TOKEN}" \
  "${BASE_URL}/api/recent-runs?tail=5"
