import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def write_file(path: Path, text: str = "x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class CleanRuntimeE2ETests(unittest.TestCase):
    def test_clean_runtime_preserves_current_label_and_removes_stale_external_roots(self):
        repo_root = Path(__file__).resolve().parents[2]
        script = repo_root / "scripts" / "ops" / "clean_runtime.py"
        now_epoch = 1_000_000

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            current_launchd = root / "external" / "launchd" / "local.apple-notes-snapshot"
            browser_user_data = root / "external" / "browser" / "chrome-user-data"
            stale_browser = root / "external" / "browser" / "tmp" / "clone-a"
            stale_runtime = root / "legacy" / "runtime" / "stale-instance"
            vendor_current = root / "external" / "vendor-runtime" / "current"

            for target in (current_launchd, browser_user_data, stale_browser, stale_runtime, vendor_current):
                write_file(target / "marker.txt")

            for target in (current_launchd, browser_user_data, stale_browser, stale_runtime, vendor_current):
                os.utime(target, (0, 0))

            base_args = [
                sys.executable,
                str(script),
                "--repo-root",
                str(root / "repo"),
                "--launchd-root",
                str(root / "external" / "launchd"),
                "--runtime-root",
                str(root / "external" / "runtime"),
                "--repos-root",
                str(root / "external" / "repos"),
                "--legacy-launchd-root",
                str(root / "legacy" / "launchd"),
                "--legacy-runtime-root",
                str(root / "legacy" / "runtime"),
                "--legacy-repos-root",
                str(root / "legacy" / "repos"),
                "--vendor-runtime-root",
                str(root / "external" / "vendor-runtime"),
                "--legacy-vendor-runtime-root",
                str(root / "legacy" / "vendor-runtime"),
                "--browser-root",
                str(root / "external" / "browser"),
                "--browser-user-data-root",
                str(browser_user_data),
                "--browser-temp-root",
                str(root / "external" / "browser" / "tmp"),
                "--current-label",
                "local.apple-notes-snapshot",
                "--retention-hours",
                "72",
                "--browser-retention-hours",
                "24",
                "--max-external-bytes",
                "1024",
                "--now-epoch",
                str(now_epoch),
            ]

            dry_run = subprocess.run(
                [*base_args, "--dry-run"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
            self.assertIn("class=external-launchd", dry_run.stdout)
            self.assertIn("action=skip_current", dry_run.stdout)
            self.assertIn("class=external-browser-temp", dry_run.stdout)
            self.assertIn("action=would_remove", dry_run.stdout)
            self.assertTrue(current_launchd.exists())
            self.assertTrue(browser_user_data.exists())
            self.assertTrue(stale_browser.exists())

            apply_run = subprocess.run(
                [*base_args, "--apply", "--include-vendor-runtime"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(apply_run.returncode, 0, apply_run.stderr)
            self.assertTrue(current_launchd.exists())
            self.assertTrue(browser_user_data.exists())
            self.assertFalse(stale_browser.exists())
            self.assertFalse(stale_runtime.exists())
            self.assertFalse(vendor_current.exists())


if __name__ == "__main__":
    unittest.main()
