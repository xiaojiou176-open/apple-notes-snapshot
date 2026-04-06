import subprocess
import unittest
from pathlib import Path


class CleanCacheHelpContractTests(unittest.TestCase):
    def test_notesctl_help_clean_cache_is_productized(self):
        repo_root = Path(__file__).resolve().parents[2]

        help_topic = subprocess.run(
            [str(repo_root / "notesctl"), "help", "clean-cache"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(help_topic.returncode, 0, help_topic.stderr)
        self.assertIn("maintainer-only repo-local cleanup", help_topic.stdout.lower())
        self.assertIn("never deletes exported snapshots", help_topic.stdout.lower())
        self.assertIn("./notesctl clean-cache --dry-run", help_topic.stdout)

        inline_help = subprocess.run(
            [str(repo_root / "notesctl"), "clean-cache", "--help"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(inline_help.returncode, 0, inline_help.stderr)
        self.assertIn("./notesctl clean-cache [--apply]", inline_help.stdout)
        self.assertIn("maintainer-only cleanup lane", inline_help.stdout.lower())
        self.assertNotIn("scripts/ops/clean_cache.zsh", inline_help.stdout)


if __name__ == "__main__":
    unittest.main()
