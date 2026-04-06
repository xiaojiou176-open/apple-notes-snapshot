import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RotateLogsE2ETests(unittest.TestCase):
    def test_rotate_structured_jsonl(self):
        repo_root = Path(__file__).resolve().parents[2]
        script = repo_root / "scripts" / "ops" / "rotate_logs.zsh"

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            state_dir = log_dir / "state"
            log_dir.mkdir(parents=True, exist_ok=True)
            state_dir.mkdir(parents=True, exist_ok=True)

            structured = log_dir / "structured.jsonl"
            structured.write_text("x" * 10, encoding="utf-8")
            (log_dir / "structured.jsonl.1").write_text("old", encoding="utf-8")
            (log_dir / "structured.jsonl.2").write_text("stale", encoding="utf-8")

            env = os.environ.copy()
            env.update(
                {
                    "NOTES_SNAPSHOT_LOG_DIR": str(log_dir),
                    "NOTES_SNAPSHOT_STATE_DIR": str(state_dir),
                }
            )

            result = subprocess.run(
                ["/bin/zsh", str(script), "--structured", "--max-bytes", "1", "--backups", "1"],
                env=env,
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((log_dir / "structured.jsonl.1").exists())
            self.assertFalse((log_dir / "structured.jsonl.2").exists())
            self.assertEqual(structured.read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()
