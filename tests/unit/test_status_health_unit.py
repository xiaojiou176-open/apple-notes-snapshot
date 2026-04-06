import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


class StatusHealthUnitTests(unittest.TestCase):
    def test_status_marks_no_success_record_as_warn_and_exposes_state_layers(self):
        repo_root = Path(__file__).resolve().parents[2]
        script = repo_root / "scripts" / "core" / "status_notes_snapshot.zsh"

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            log_dir = temp_root / "logs"
            state_dir = temp_root / "state"
            log_dir.mkdir(parents=True, exist_ok=True)
            state_dir.mkdir(parents=True, exist_ok=True)

            env = os.environ.copy()
            env.update(
                {
                    "NOTES_SNAPSHOT_ROOT_DIR": str(temp_root / "exports"),
                    "NOTES_SNAPSHOT_LOG_DIR": str(log_dir),
                    "NOTES_SNAPSHOT_STATE_DIR": str(state_dir),
                    "NOTES_SNAPSHOT_TAIL_LINES": "20",
                    "NOTES_SNAPSHOT_STALE_THRESHOLD_SEC": "7200",
                    "NOTES_SNAPSHOT_INTERVAL_MINUTES": "30",
                    "NOTES_SNAPSHOT_PREFER_STATE_JSON": "1",
                    "NOTES_SNAPSHOT_LAUNCHD_LABEL": "local.apple-notes-snapshot.test-no-success",
                }
            )

            result = subprocess.run(
                ["/bin/zsh", str(script), "--json"],
                env=env,
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("health_level"), "WARN")
            self.assertIn("unknown_last_success", payload.get("health_reasons", []))
            self.assertIn("first successful snapshot baseline", payload.get("health_summary", ""))
            state_layers = payload.get("state_layers", {})
            self.assertEqual(state_layers.get("config", {}).get("status"), "configured")
            self.assertEqual(state_layers.get("launchd", {}).get("status"), "not_loaded")
            self.assertEqual(state_layers.get("ledger", {}).get("status"), "needs_first_run")
            self.assertIn("No successful snapshot", state_layers.get("ledger", {}).get("summary", ""))

    def test_status_degrades_on_checksum_missing_and_runtime_log_errors(self):
        repo_root = Path(__file__).resolve().parents[2]
        script = repo_root / "scripts" / "core" / "status_notes_snapshot.zsh"

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            log_dir = temp_root / "logs"
            state_dir = temp_root / "state"
            log_dir.mkdir(parents=True, exist_ok=True)
            state_dir.mkdir(parents=True, exist_ok=True)

            now_epoch = int(time.time())
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_epoch))
            state_json = state_dir / "state.json"
            state_json.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "exit_code": 0,
                        "schema_version": 1,
                        "duration_sec": 1,
                        "start_epoch": now_epoch - 1,
                        "start_iso": now_iso,
                        "end_epoch": now_epoch,
                        "end_iso": now_iso,
                        "pid": 123,
                        "root_dir": "/tmp/export-root",
                        "exporter_script": "/tmp/exportnotes.zsh",
                        "last_success_iso": now_iso,
                        "last_success_epoch": now_epoch,
                        "trigger_source": "launchd",
                        "run_id": "rid-1",
                    }
                ),
                encoding="utf-8",
            )
            (state_dir / "metrics.jsonl").write_text("", encoding="utf-8")
            (log_dir / "stderr.log").write_text(
                "command not found: python\n"
                "osascript: /tmp/export_notes.scpt: No such file or directory\n",
                encoding="utf-8",
            )
            (log_dir / "stdout.log").write_text("", encoding="utf-8")
            (log_dir / "launchd.err.log").write_text("", encoding="utf-8")

            env = os.environ.copy()
            env.update(
                {
                    "NOTES_SNAPSHOT_LOG_DIR": str(log_dir),
                    "NOTES_SNAPSHOT_STATE_DIR": str(state_dir),
                    "NOTES_SNAPSHOT_TAIL_LINES": "20",
                    "NOTES_SNAPSHOT_STALE_THRESHOLD_SEC": "7200",
                    "NOTES_SNAPSHOT_INTERVAL_MINUTES": "30",
                    "NOTES_SNAPSHOT_PREFER_STATE_JSON": "1",
                }
            )

            result = subprocess.run(
                ["/bin/zsh", str(script), "--json"],
                env=env,
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertLess(payload.get("health_score", 100), 100)
            self.assertNotEqual(payload.get("health_level"), "OK")
            self.assertIn("checksum_missing", payload.get("health_reasons", []))
            self.assertIn("log_health_errors", payload.get("health_reasons", []))
            self.assertGreater(payload.get("log_health", {}).get("errors_total", 0), 0)


if __name__ == "__main__":
    unittest.main()
