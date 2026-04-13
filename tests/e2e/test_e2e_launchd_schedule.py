import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


class LaunchdScheduleE2ETests(unittest.TestCase):
    def setUp(self):
        if shutil.which("launchctl") is None:
            self.fail("launchctl not found; launchd e2e requires macOS")

    def test_launchd_schedule_triggers_second_run(self):
        repo_root = Path(__file__).resolve().parents[2]

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir) / "repo"
            temp_root.mkdir(parents=True, exist_ok=True)

            for name in ("notesctl", "scripts", "config", "generated"):
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
  /bin/mkdir -p -- "$root"
  /bin/date +%s >> "$root/run_log.txt"
  echo "ok" > "$root/e2e_marker.txt"
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

            label = f"local.apple-notes-snapshot.e2e.schedule.{os.getpid()}"
            web_label = f"{label}.webui"
            plist_path = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"

            env = os.environ.copy()
            env.update(
                {
                    "NOTES_SNAPSHOT_ROOT_DIR": str(root_dir),
                    "NOTES_SNAPSHOT_DIR": str(vendor_dir),
                    "NOTES_SNAPSHOT_LOG_DIR": str(log_dir),
                    "NOTES_SNAPSHOT_STATE_DIR": str(state_dir),
                    "NOTES_SNAPSHOT_INTERVAL_MINUTES": "1",
                    "NOTES_SNAPSHOT_TIMEOUT_SEC": "10",
                    "NOTES_SNAPSHOT_WEB_ENABLE": "0",
                    "NOTES_SNAPSHOT_LAUNCHD_LABEL": label,
                    "NOTES_SNAPSHOT_LAUNCHD_WEB_LABEL": web_label,
                }
            )
            env["PATH"] = f"/usr/bin:/bin:/usr/sbin:/sbin:{env.get('PATH','')}"

            # Persist overrides for launchd runtime (launchd won't inherit test env)
            env_file = temp_root / "config" / "notes_snapshot.env"
            env_file.write_text(
                "\n".join(
                    [
                        f'NOTES_SNAPSHOT_ROOT_DIR="{root_dir}"',
                        f'NOTES_SNAPSHOT_DIR="{vendor_dir}"',
                        f'NOTES_SNAPSHOT_LOG_DIR="{log_dir}"',
                        f'NOTES_SNAPSHOT_STATE_DIR="{state_dir}"',
                        'NOTES_SNAPSHOT_INTERVAL_MINUTES="1"',
                        'NOTES_SNAPSHOT_TIMEOUT_SEC="10"',
                        'NOTES_SNAPSHOT_WEB_ENABLE="0"',
                        f'NOTES_SNAPSHOT_LAUNCHD_LABEL="{label}"',
                        f'NOTES_SNAPSHOT_LAUNCHD_WEB_LABEL="{web_label}"',
                    ]
                ) + "\n",
                encoding="utf-8",
            )

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

            def launchctl_print():
                return subprocess.run(
                    ["launchctl", "print", f"{domain}/{label}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )

            def status_payload():
                result = run_cmd(["status", "--json"], check=True)
                return json.loads(result.stdout)

            def run_log_lines(path: Path) -> int:
                if not path.exists():
                    return 0
                content = path.read_text(encoding="utf-8").strip().splitlines()
                if content == [""]:
                    return 0
                return len(content)

            def wait_for(condition, timeout_sec: int, interval_sec: float, message: str):
                deadline = time.monotonic() + timeout_sec
                latest = None
                while time.monotonic() < deadline:
                    latest = condition()
                    if latest:
                        return latest
                    time.sleep(interval_sec)
                self.fail(message)

            run_log = root_dir / "run_log.txt"
            state_json = state_dir / "state.json"

            try:
                run_cmd(["install", "--minutes", "1", "--load", "--no-web"], check=True)

                # Wait for initial kickstart run to fully settle. The exporter writes
                # its marker before the wrapper flips state.json from running to success.
                baseline_payload = wait_for(
                    lambda: (
                        payload
                        if (
                            run_log_lines(run_log) >= 1
                            and state_json.exists()
                            and (payload := status_payload()).get("status") == "success"
                            and payload.get("last_success_iso")
                            not in (None, "", "unknown")
                        )
                        else None
                    ),
                    timeout_sec=20,
                    interval_sec=1,
                    message="initial launchd run did not settle to success",
                )
                first_count = run_log_lines(run_log)
                self.assertGreaterEqual(first_count, 1, "initial launchd run did not complete")
                baseline_last_success = baseline_payload["last_success_iso"]

                # Wait for the scheduled second run to finish, not merely start.
                payload = wait_for(
                    lambda: (
                        current
                        if (
                            run_log_lines(run_log) >= first_count + 1
                            and (current := status_payload()).get("status") == "success"
                            and current.get("last_success_iso")
                            not in (None, "", "unknown", baseline_last_success)
                        )
                        else None
                    ),
                    timeout_sec=90,
                    interval_sec=2,
                    message="launchd did not complete a second successful run within 90s",
                )
                self.assertEqual(payload.get("status"), "success")
                self.assertNotEqual(payload.get("last_success_iso"), baseline_last_success)
                self.assertEqual(payload.get("trigger_source"), "launchd")
                if state_json.exists():
                    data = json.loads(state_json.read_text(encoding="utf-8"))
                    self.assertEqual(data.get("trigger_source"), "launchd")
                    self.assertEqual(data.get("status"), "success")
                    self.assertNotEqual(data.get("last_success_iso"), baseline_last_success)

                info = launchctl_print()
                self.assertEqual(info.returncode, 0, info.stderr)
                self.assertIn(label, info.stdout)

                ensure = run_cmd(["ensure", "--json"], check=True)
                ensure_payload = json.loads(ensure.stdout)
                self.assertIn(ensure_payload.get("action"), ("ok", "reinstalled"))
            finally:
                run_cmd(["install", "--unload", "--no-web"], check=False)
                subprocess.run(["launchctl", "bootout", domain, str(plist_path)], capture_output=True)
                if plist_path.exists():
                    try:
                        plist_path.unlink()
                    except OSError:
                        pass


if __name__ == "__main__":
    unittest.main()
