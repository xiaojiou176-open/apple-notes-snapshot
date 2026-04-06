import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


class LaunchdE2ETests(unittest.TestCase):
    def setUp(self):
        if shutil.which("launchctl") is None:
            self.fail("launchctl not found; launchd e2e requires macOS")

    def test_launchd_install_and_run(self):
        repo_root = Path(__file__).resolve().parents[2]

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir) / "repo"
            temp_root.mkdir(parents=True, exist_ok=True)

            # Copy minimal repo structure
            for name in ("notesctl", "scripts", "config", "generated"):
                src = repo_root / name
                dst = temp_root / name
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

            # Stub vendor exporter
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

            label = f"local.apple-notes-snapshot.e2e.{os.getpid()}"
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

            try:
                # Run export (full wrapper) and verify state
                run_cmd(["run", "--no-status"], check=True)
                state_json = state_dir / "state.json"
                self.assertTrue(state_json.is_file())
                data = json.loads(state_json.read_text(encoding="utf-8"))
                self.assertEqual(data.get("status"), "success")
                self.assertEqual(data.get("trigger_source"), "manual")
                self.assertTrue((root_dir / "e2e_marker.txt").exists())

                # Install + load launchd job
                run_cmd(["install", "--minutes", "1", "--load", "--no-web"], check=True)

                info = launchctl_print()
                self.assertEqual(info.returncode, 0, info.stderr)
                self.assertIn(label, info.stdout)

                # Ensure config
                result = run_cmd(["ensure", "--json"], check=True)
                payload = json.loads(result.stdout)
                self.assertIn(payload.get("action"), ("ok", "reinstalled"))

                # Unload
                run_cmd(["install", "--unload", "--no-web"], check=True)
                time.sleep(0.2)

                info = launchctl_print()
                self.assertNotEqual(info.returncode, 0)
            finally:
                # Cleanup launchd plist
                subprocess.run(["launchctl", "bootout", domain, str(plist_path)], capture_output=True)
                if plist_path.exists():
                    try:
                        plist_path.unlink()
                    except OSError:
                        pass


if __name__ == "__main__":
    unittest.main()
