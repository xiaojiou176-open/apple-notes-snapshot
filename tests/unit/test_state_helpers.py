import json
import subprocess
import tempfile
import unittest
import sys
from pathlib import Path


class StateHelperTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[2]
        self.common = self.repo_root / "scripts" / "lib" / "common.zsh"
        self.state = self.repo_root / "scripts" / "lib" / "state.zsh"
        self.config = self.repo_root / "scripts" / "lib" / "config.zsh"

    def run_zsh(self, script):
        return subprocess.run(
            ["/bin/zsh", "-c", script],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_phases_json_and_summary(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
            tmp.write("phase=export duration_sec=12\n")
            tmp.write("phase=convert duration_sec=3\n")
            path = tmp.name
        try:
            script = f"""
            set -euo pipefail
            source "{self.state}"
            json_out="$(state_build_phases_json \"{path}\")"
            summary_out="$(state_build_phases_summary \"{path}\")"
            print -r -- "$json_out"
            print -r -- "$summary_out"
            """
            result = self.run_zsh(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = [line for line in result.stdout.splitlines() if line.strip()]
            self.assertGreaterEqual(len(lines), 2)
            phases = json.loads(lines[0])
            self.assertEqual(phases.get("export"), 12)
            self.assertEqual(phases.get("convert"), 3)
            self.assertIn("export:12", lines[1])
            self.assertIn("convert:3", lines[1])
        finally:
            try:
                Path(path).unlink()
            except FileNotFoundError:
                # Cleanup is best-effort; the temp file may already be gone.
                pass

    def test_state_json_warning_and_trigger_source(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
            tmp.write('{"end_iso": "2024-01-01T00:00:00Z", "trigger_source": "web:run", "run_id": "rid-1"}')
            path = tmp.name
        try:
            python_bin = sys.executable
            script = f"""
            set -euo pipefail
            source "{self.state}"
            export NOTES_SNAPSHOT_PYTHON_BIN="{python_bin}"
            state_load_state_json "{path}"
            print -r -- "${{state_json_warning:-}}"
            print -r -- "${{trigger_source:-}}"
            print -r -- "${{run_id:-}}"
            """
            result = self.run_zsh(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = [line for line in result.stdout.splitlines() if line.strip()]
            self.assertGreaterEqual(len(lines), 3)
            self.assertIn("missing_fields", lines[0])
            self.assertEqual(lines[1], "web:run")
            self.assertEqual(lines[2], "rid-1")
        finally:
            try:
                Path(path).unlink()
            except FileNotFoundError:
                # Cleanup is best-effort; the temp file may already be gone.
                pass

    def test_state_json_checksum(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
            path = tmp.name
        try:
            python_bin = sys.executable
            script = f"""
            set -euo pipefail
            source "{self.state}"
            export NOTES_SNAPSHOT_PYTHON_BIN="{python_bin}"
            STATE_SCHEMA_VERSION="1"
            state_write_state_json "{path}" "success" 0 5 1 "2024-01-01T00:00:00Z" 2 "2024-01-01T00:00:05Z" "/tmp" "/tmp/exportnotes.zsh" 123 "2024-01-01T00:00:00Z"
            /bin/cat "{path}"
            """
            result = self.run_zsh(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertTrue(data.get("checksum"))
            checksum = data.get("checksum")
            data.pop("checksum", None)
            canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
            import hashlib
            self.assertEqual(hashlib.sha256(canonical).hexdigest(), checksum)
        finally:
            try:
                Path(path).unlink()
            except FileNotFoundError:
                # Cleanup is best-effort; the temp file may already be gone.
                pass

    def test_state_json_checksum_without_explicit_python_override(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
            path = tmp.name
        try:
            python_dir = Path(sys.executable).resolve().parent
            script = f"""
            set -euo pipefail
            source "{self.common}"
            ENV_FILE="{self.repo_root}/config/notes_snapshot.env"
            REPO_ROOT="{self.repo_root}"
            source "{self.config}"
            source "{self.state}"
            unset NOTES_SNAPSHOT_PYTHON_BIN
            export PATH="{python_dir}:$PATH"
            load_env_with_defaults
            STATE_SCHEMA_VERSION="1"
            state_write_state_json "{path}" "success" 0 5 1 "2024-01-01T00:00:00Z" 2 "2024-01-01T00:00:05Z" "/tmp" "/tmp/exportnotes.zsh" 123 "2024-01-01T00:00:00Z"
            /bin/cat "{path}"
            """
            result = self.run_zsh(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertTrue(data.get("checksum"))
        finally:
            try:
                Path(path).unlink()
            except FileNotFoundError:
                # Cleanup is best-effort; the temp file may already be gone.
                pass

    def test_state_json_checksum_uses_python_bin_fallback(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
            path = tmp.name
        try:
            python_bin = sys.executable
            script = f"""
            set -euo pipefail
            source "{self.common}"
            ENV_FILE="{self.repo_root}/config/notes_snapshot.env"
            REPO_ROOT="/tmp/nonexistent-repo-root-for-python-fallback"
            source "{self.config}"
            source "{self.state}"
            unset NOTES_SNAPSHOT_PYTHON_BIN
            export PYTHON_BIN="{python_bin}"
            load_env_with_defaults
            STATE_SCHEMA_VERSION="1"
            state_write_state_json "{path}" "success" 0 5 1 "2024-01-01T00:00:00Z" 2 "2024-01-01T00:00:05Z" "/tmp" "/tmp/exportnotes.zsh" 123 "2024-01-01T00:00:00Z"
            /bin/cat "{path}"
            """
            result = self.run_zsh(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertTrue(data.get("checksum"))
        finally:
            try:
                Path(path).unlink()
            except FileNotFoundError:
                # Cleanup is best-effort; the temp file may already be gone.
                pass


if __name__ == "__main__":
    unittest.main()
