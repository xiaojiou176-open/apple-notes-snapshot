import unittest
from pathlib import Path


class ZeroCliInstallContractTests(unittest.TestCase):
    def test_zero_cli_install_avoids_desktop_control_primitives(self):
        repo_root = Path(__file__).resolve().parents[2]
        content = (repo_root / "scripts" / "ops" / "zero_cli_install.zsh").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("/usr/bin/osascript", content)
        self.assertNotIn('tell application "System Events"', content)
        self.assertNotIn("display notification", content)

        self.assertIn('"$REPO_ROOT/notesctl" install --minutes "$NOTES_SNAPSHOT_INTERVAL_MINUTES" --load --web', content)
        self.assertIn("Skipping login-item automation for host safety.", content)


if __name__ == "__main__":
    unittest.main()
