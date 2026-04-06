import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class DoctorStateLayersUnitTests(unittest.TestCase):
    def test_doctor_exposes_state_layers_and_first_run_summary_without_missing_dir_noise(self):
        repo_root = Path(__file__).resolve().parents[2]
        script = repo_root / "scripts" / "core" / "doctor_notes_snapshot.zsh"

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            root_dir = temp_root / "exports"
            root_dir.mkdir(parents=True, exist_ok=True)

            env = os.environ.copy()
            env.update(
                {
                    "NOTES_SNAPSHOT_ROOT_DIR": str(root_dir),
                    "NOTES_SNAPSHOT_LOG_DIR": str(temp_root / "logs"),
                    "NOTES_SNAPSHOT_STATE_DIR": str(temp_root / "state"),
                    "NOTES_SNAPSHOT_INTERVAL_MINUTES": "30",
                    "NOTES_SNAPSHOT_PREFER_STATE_JSON": "1",
                    "NOTES_SNAPSHOT_LAUNCHD_LABEL": "local.apple-notes-snapshot.test-doctor-state-layers",
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

            self.assertIn("first-run or cleaned-checkout baseline", payload.get("operator_summary", ""))
            state_layers = payload.get("state_layers", {})
            self.assertEqual(state_layers.get("config", {}).get("status"), "configured")
            self.assertEqual(state_layers.get("ledger", {}).get("status"), "needs_first_run")
            self.assertIn("No successful snapshot", state_layers.get("ledger", {}).get("summary", ""))

            warnings = payload.get("warnings", [])
            self.assertTrue(any("no successful snapshot recorded yet" in warning for warning in warnings))
            self.assertFalse(any("log dir missing" in warning for warning in warnings))
            self.assertFalse(any("state dir missing" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
