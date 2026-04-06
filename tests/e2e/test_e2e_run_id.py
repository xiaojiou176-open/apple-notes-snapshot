import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunIdE2ETests(unittest.TestCase):
    def test_run_id_correlates_metrics_and_structured_logs(self):
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
  mkdir -p -- "$root"
  echo "ok" > "$root/run_id_marker.txt"
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
            lock_dir = temp_root / "_lock"
            lock_file = temp_root / "_lockfile"
            root_dir.mkdir(parents=True, exist_ok=True)
            state_dir.mkdir(parents=True, exist_ok=True)

            env = os.environ.copy()
            env.update(
                {
                    "NOTES_SNAPSHOT_ROOT_DIR": str(root_dir),
                    "NOTES_SNAPSHOT_DIR": str(vendor_dir),
                    "NOTES_SNAPSHOT_LOG_DIR": str(log_dir),
                    "NOTES_SNAPSHOT_STATE_DIR": str(state_dir),
                    "NOTES_SNAPSHOT_LOCK_DIR": str(lock_dir),
                    "NOTES_SNAPSHOT_LOCK_FILE": str(lock_file),
                    "NOTES_SNAPSHOT_WEB_ENABLE": "0",
                    "NOTES_SNAPSHOT_LOG_JSONL": "1",
                }
            )
            env["PATH"] = f"/usr/bin:/bin:/usr/sbin:/sbin:{env.get('PATH','')}"

            wrapper = temp_root / "scripts" / "core" / "notes_snapshot_wrapper.zsh"

            result = subprocess.run(
                ["/bin/zsh", str(wrapper)],
                env=env,
                cwd=str(temp_root),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            metrics_path = state_dir / "metrics.jsonl"
            structured_path = log_dir / "structured.jsonl"
            self.assertTrue(metrics_path.is_file())
            self.assertTrue(structured_path.is_file())

            metrics_lines = [
                json.loads(line)
                for line in metrics_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            start = next((line for line in metrics_lines if line.get("event") == "run_start"), None)
            end = next((line for line in metrics_lines if line.get("event") == "run_end"), None)
            self.assertIsNotNone(start)
            self.assertIsNotNone(end)
            self.assertTrue(start.get("run_id"))
            self.assertEqual(start.get("run_id"), end.get("run_id"))

            structured_lines = [
                json.loads(line)
                for line in structured_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            correlated = [line for line in structured_lines if line.get("run_id") == start.get("run_id")]
            self.assertTrue(correlated, "structured.jsonl missing run_id correlation")


if __name__ == "__main__":
    unittest.main()
