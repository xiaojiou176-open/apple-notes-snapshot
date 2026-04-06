import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class TimeoutE2ETests(unittest.TestCase):
    def test_timeout_marks_failure_reason(self):
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
/bin/sleep 3
exit 0
""",
                encoding="utf-8",
            )
            exporter.chmod(0o755)

            bin_dir = temp_root / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            timeout_bin = bin_dir / "timeout"
            timeout_bin.write_text(
                """#!/usr/bin/env python3
import subprocess
import sys

if len(sys.argv) < 3:
    sys.exit(125)

try:
    sec = float(sys.argv[1])
except Exception:
    sys.exit(125)

cmd = sys.argv[2:]
proc = subprocess.Popen(cmd)
try:
    proc.wait(timeout=sec)
    sys.exit(proc.returncode)
except subprocess.TimeoutExpired:
    try:
        proc.kill()
    except Exception:
        pass
    sys.exit(124)
""",
                encoding="utf-8",
            )
            timeout_bin.chmod(0o755)

            root_dir = temp_root / "_root"
            log_dir = temp_root / "_logs"
            state_dir = log_dir / "state"
            root_dir.mkdir(parents=True, exist_ok=True)
            state_dir.mkdir(parents=True, exist_ok=True)
            lock_dir = temp_root / "_lock"
            lock_file = temp_root / "_lockfile"

            env = os.environ.copy()
            env.update(
                {
                    "NOTES_SNAPSHOT_ROOT_DIR": str(root_dir),
                    "NOTES_SNAPSHOT_DIR": str(vendor_dir),
                    "NOTES_SNAPSHOT_LOG_DIR": str(log_dir),
                    "NOTES_SNAPSHOT_STATE_DIR": str(state_dir),
                    "NOTES_SNAPSHOT_TIMEOUT_SEC": "1",
                    "NOTES_SNAPSHOT_LOCK_DIR": str(lock_dir),
                    "NOTES_SNAPSHOT_LOCK_FILE": str(lock_file),
                    "NOTES_SNAPSHOT_WEB_ENABLE": "0",
                }
            )
            env["PATH"] = f"{bin_dir}:/usr/bin:/bin:/usr/sbin:/sbin:{env.get('PATH','')}"

            wrapper = temp_root / "scripts" / "core" / "notes_snapshot_wrapper.zsh"

            result = subprocess.run(
                ["/bin/zsh", str(wrapper)],
                env=env,
                cwd=str(temp_root),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertIn(result.returncode, (124, 137))

            state_json = state_dir / "state.json"
            self.assertTrue(state_json.is_file(), result.stderr)
            data = json.loads(state_json.read_text(encoding="utf-8"))
            self.assertEqual(data.get("status"), "failed")
            self.assertEqual(data.get("failure_reason"), "timeout")
            self.assertIn(data.get("exit_code"), (124, 137))


if __name__ == "__main__":
    unittest.main()
