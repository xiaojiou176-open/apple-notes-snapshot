import subprocess
import unittest
from pathlib import Path


class LaunchdHelperTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[2]
        self.common = self.repo_root / "scripts" / "lib" / "common.zsh"
        self.launchd = self.repo_root / "scripts" / "lib" / "launchd.zsh"

    def run_zsh(self, script):
        return subprocess.run(
            ["/bin/zsh", "-c", script],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_build_schedule_block_calendar(self):
        script = f"""
        set -euo pipefail
        source "{self.common}"
        source "{self.launchd}"
        launchd_build_schedule_block 1800 ""
        """
        result = self.run_zsh(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("StartCalendarInterval", result.stdout)

    def test_build_schedule_block_interval(self):
        script = f"""
        set -euo pipefail
        source "{self.common}"
        source "{self.launchd}"
        launchd_build_schedule_block 600 ""
        """
        result = self.run_zsh(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("StartInterval", result.stdout)
        self.assertIn("600", result.stdout)

    def test_build_paths_block(self):
        script = f"""
        set -euo pipefail
        source "{self.common}"
        source "{self.launchd}"
        launchd_build_paths_block "WatchPaths" "/tmp/a,/tmp/b"
        """
        result = self.run_zsh(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WatchPaths", result.stdout)
        self.assertIn("/tmp/a", result.stdout)
        self.assertIn("/tmp/b", result.stdout)

    def test_runtime_repo_root_avoids_spaces(self):
        script = f"""
        set -euo pipefail
        source "{self.common}"
        source "{self.launchd}"
        repo_root="$(launchd_runtime_repo_root "local.apple-notes-snapshot")"
        print -r -- "$repo_root"
        """
        result = self.run_zsh(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1)
        self.assertIn("/.cache/apple-notes-snapshot/repos/", lines[0])
        self.assertNotIn("ApplicationSupport", lines[0])


if __name__ == "__main__":
    unittest.main()
