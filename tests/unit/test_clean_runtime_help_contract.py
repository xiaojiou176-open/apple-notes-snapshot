import subprocess
import unittest
from pathlib import Path


class CleanRuntimeHelpContractTests(unittest.TestCase):
    def test_clean_runtime_help_explains_external_repo_owned_boundary(self):
        repo_root = Path(__file__).resolve().parents[2]

        help_topic = subprocess.run(
            [str(repo_root / "notesctl"), "help", "clean-runtime"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(help_topic.returncode, 0, help_topic.stderr)
        self.assertIn("maintainer-only external repo-owned cleanup", help_topic.stdout.lower())
        self.assertIn("repo-managed machine cache root for launchd, runtime, repo copies, and disposable browser temp state", help_topic.stdout)
        self.assertIn("repo-managed isolated browser root is always protected", help_topic.stdout)

        inline_help = subprocess.run(
            [str(repo_root / "notesctl"), "clean-runtime", "--help"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(inline_help.returncode, 0, inline_help.stderr)
        self.assertIn("./notesctl clean-runtime --dry-run", inline_help.stdout)
        self.assertIn("Docker / clean-room / runner-temp / shared tool caches", inline_help.stdout)


if __name__ == "__main__":
    unittest.main()
