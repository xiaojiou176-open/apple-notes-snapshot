#!/bin/zsh
set -euo pipefail

REPO_ROOT="${0:A:h:h:h}"
BUNDLE_TEMPLATE_DIR="${REPO_ROOT}/packaging/mcpb"
STAGE_ROOT="${REPO_ROOT}/.runtime-cache/mcp-registry-lane"
STAGE_DIR="${STAGE_ROOT}/bundle-src"
OUT_DIR="${STAGE_ROOT}/out"

if command -v mcpb >/dev/null 2>&1; then
  mcpb_cmd=(mcpb)
else
  mcpb_cmd=(npx -y @anthropic-ai/mcpb)
fi

version_tag="${VERSION_TAG:-}"
if [[ -z "${version_tag}" ]]; then
  version_tag="$(git -C "${REPO_ROOT}" describe --tags --abbrev=0 2>/dev/null || echo "v0.1.12")"
fi
version="${version_tag#v}"
artifact_name="apple-notes-snapshot-control-room-${version_tag}.mcpb"
artifact_path="${OUT_DIR}/${artifact_name}"
metadata_path="${OUT_DIR}/${artifact_name:r}.metadata.json"
server_json_path="${REPO_ROOT}/server.json"

rm -rf "${STAGE_DIR}"
mkdir -p "${STAGE_DIR}" "${OUT_DIR}"

for rel in LICENSE README.md notesctl config scripts; do
  rsync -a "${REPO_ROOT}/${rel}" "${STAGE_DIR}/"
done

cp "${BUNDLE_TEMPLATE_DIR}/manifest.json" "${STAGE_DIR}/manifest.json"

"${mcpb_cmd[@]}" validate "${STAGE_DIR}"
"${mcpb_cmd[@]}" pack "${STAGE_DIR}" "${artifact_path}"

sha256="$(shasum -a 256 "${artifact_path}" | awk '{print $1}')"
release_url="https://github.com/xiaojiou176-open/apple-notes-snapshot/releases/download/${version_tag}/${artifact_name}"

python3 - <<PY
import json
from pathlib import Path

metadata = {
    "artifact": "${artifact_name}",
    "artifact_path": "${artifact_path}",
    "sha256": "${sha256}",
    "version": "${version}",
    "version_tag": "${version_tag}",
    "release_url": "${release_url}",
}
Path("${metadata_path}").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

server_json_path = Path("${server_json_path}")
if server_json_path.exists():
    payload = json.loads(server_json_path.read_text(encoding="utf-8"))
    payload["version"] = "${version}"
    package = payload["packages"][0]
    package["identifier"] = "${release_url}"
    package["fileSha256"] = "${sha256}"
    server_json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY

rm -rf "${STAGE_DIR}"

printf 'artifact=%s\n' "${artifact_path}"
printf 'sha256=%s\n' "${sha256}"
printf 'release_url=%s\n' "${release_url}"
printf 'metadata=%s\n' "${metadata_path}"
