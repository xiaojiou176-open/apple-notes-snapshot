import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class LaunchdWebE2ETests(unittest.TestCase):
    def setUp(self):
        if shutil.which("launchctl") is None:
            self.fail("launchctl not found; launchd e2e requires macOS")

    def wait_for_server(self, port, headers=None, expected_status=200):
        deadline = time.time() + 8
        last_error = None
        while time.time() < deadline:
            try:
                req = Request(f"http://127.0.0.1:{port}/api/health", headers=headers or {})
                with urlopen(req, timeout=1) as resp:
                    if resp.status == expected_status:
                        return
            except HTTPError as exc:
                last_error = exc
            except Exception as exc:
                last_error = exc
            time.sleep(0.2)
        raise AssertionError(f"web ui not ready: {last_error}")

    def request_json(self, url, headers=None, payload=None, method=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = Request(url, data=data, headers=headers or {}, method=method)
        try:
            with urlopen(req, timeout=3) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8")
            try:
                payload = json.loads(body)
            except Exception:
                payload = {"raw": body}
            return exc.code, payload

    def wait_for_trigger(self, path, expected, timeout=8):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if path.is_file():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if data.get("trigger_source") == expected:
                        return data
                except Exception:
                    pass
            time.sleep(0.2)
        raise AssertionError("state.json not updated with expected trigger")

    def test_launchd_webui_run_action(self):
        repo_root = Path(__file__).resolve().parents[2]

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir) / "repo"
            temp_root.mkdir(parents=True, exist_ok=True)

            for name in ("notesctl", "scripts", "config", "generated", "web"):
                src = repo_root / name
                dst = temp_root / name
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

            vendor_dir = temp_root / "vendor" / "notes-exporter"
            vendor_dir.mkdir(parents=True, exist_ok=True)
            exporter = vendor_dir / "exportnotes.zsh"
            exporter.write_text(
                """#!/bin/zsh
set -euo pipefail
root=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root-dir)
      root="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done
if [[ -n "$root" ]]; then
  mkdir -p -- "$root"
  echo "ok" > "$root/web_launchd_marker.txt"
fi
if [[ -n "${NOTES_EXPORT_METRICS_FILE:-}" ]]; then
  echo "phase=export duration_sec=1" > "$NOTES_EXPORT_METRICS_FILE"
fi
if [[ -n "${NOTES_EXPORT_PIPELINE_EXIT_REASON_FILE:-}" ]]; then
  echo "ok" > "$NOTES_EXPORT_PIPELINE_EXIT_REASON_FILE"
fi
exit 0
""",
                encoding="utf-8",
            )
            exporter.chmod(0o755)

            root_dir = temp_root / "_root"
            log_dir = temp_root / "_logs"
            state_dir = log_dir / "state"
            root_dir.mkdir(parents=True, exist_ok=True)
            state_dir.mkdir(parents=True, exist_ok=True)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]

            label = f"local.apple-notes-snapshot.e2eweb.{os.getpid()}"
            web_label = f"{label}.webui"
            plist_path = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
            web_plist_path = Path.home() / "Library" / "LaunchAgents" / f"{web_label}.plist"

            env = os.environ.copy()
            env.update(
                {
                    "NOTES_SNAPSHOT_ROOT_DIR": str(root_dir),
                    "NOTES_SNAPSHOT_DIR": str(vendor_dir),
                    "NOTES_SNAPSHOT_LOG_DIR": str(log_dir),
                    "NOTES_SNAPSHOT_STATE_DIR": str(state_dir),
                    "NOTES_SNAPSHOT_INTERVAL_MINUTES": "1",
                    "NOTES_SNAPSHOT_TIMEOUT_SEC": "10",
                    "NOTES_SNAPSHOT_WEB_ENABLE": "1",
                    "NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN": "1",
                    "NOTES_SNAPSHOT_WEB_TOKEN": "webtoken",
                    "NOTES_SNAPSHOT_WEB_TOKEN_SCOPES": "read,run",
                    "NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW": "run",
                    "NOTES_SNAPSHOT_WEB_ALLOW_REMOTE": "0",
                    "NOTES_SNAPSHOT_WEB_ALLOW_IPS": "127.0.0.1/32",
                    "NOTES_SNAPSHOT_WEB_HOST": "127.0.0.1",
                    "NOTES_SNAPSHOT_WEB_PORT": str(port),
                    "NOTES_SNAPSHOT_LAUNCHD_LABEL": label,
                    "NOTES_SNAPSHOT_LAUNCHD_WEB_LABEL": web_label,
                }
            )
            env["PATH"] = f"/usr/bin:/bin:/usr/sbin:/sbin:{env.get('PATH','')}"

            notesctl = temp_root / "notesctl"
            domain = f"gui/{os.getuid()}"

            def run_cmd(args, check=True):
                return subprocess.run(
                    [str(notesctl), *args],
                    env=env,
                    cwd=str(temp_root),
                    capture_output=True,
                    text=True,
                    check=check,
                )

            try:
                run_cmd(["install", "--minutes", "1", "--load", "--web"], check=True)

                headers = {"Authorization": "Bearer webtoken"}
                self.wait_for_server(port, headers=headers)

                status, payload = self.request_json(
                    f"http://127.0.0.1:{port}/api/run",
                    headers={"Authorization": "Bearer webtoken", "Content-Type": "application/json"},
                    payload={},
                    method="POST",
                )
                self.assertEqual(status, 200)
                self.assertTrue(payload.get("ok"))

                state_json = state_dir / "state.json"
                data = self.wait_for_trigger(state_json, "web:run")
                self.assertTrue(data.get("run_id"))
            finally:
                subprocess.run(["launchctl", "bootout", domain, str(plist_path)], capture_output=True)
                subprocess.run(["launchctl", "bootout", domain, str(web_plist_path)], capture_output=True)
                if plist_path.exists():
                    try:
                        plist_path.unlink()
                    except OSError:
                        pass
                if web_plist_path.exists():
                    try:
                        web_plist_path.unlink()
                    except OSError:
                        pass


if __name__ == "__main__":
    unittest.main()
