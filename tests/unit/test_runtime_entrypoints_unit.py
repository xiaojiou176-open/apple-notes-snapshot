import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path


def load_module(name: str, relative_path: str):
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / relative_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_file(path: Path, text: str = "x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def set_mtime(path: Path, epoch: int):
    os.utime(path, (epoch, epoch), follow_symlinks=False)


class RuntimeEntryPointUnitTests(unittest.TestCase):
    def test_runtime_audit_main_renders_text_and_json(self):
        module = load_module("runtime_audit", "scripts/ops/runtime_audit.py")
        now_epoch = 1_000_000

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_file(root / "external" / "runtime" / "recent-run" / "marker.txt")
            argv = [
                "runtime_audit.py",
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
                str(root / "external" / "browser" / "chrome-user-data"),
                "--browser-temp-root",
                str(root / "external" / "browser" / "tmp"),
                "--current-label",
                "local.apple-notes-snapshot",
                "--now-epoch",
                str(now_epoch),
            ]

            with mock.patch("sys.argv", argv):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    exit_code = module.main()
            self.assertEqual(exit_code, 0)
            self.assertIn("Apple Notes Snapshot runtime-audit", buffer.getvalue())
            self.assertIn("external_cache_roots:", buffer.getvalue())

            with mock.patch("sys.argv", [*argv, "--json"]):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    exit_code = module.main()
            self.assertEqual(exit_code, 0)
            rendered = json.loads(buffer.getvalue())
            self.assertIn("repo_local", rendered)
            self.assertIn("external_cache", rendered)

    def test_clean_runtime_main_supports_dry_run_apply_and_quiet_auto(self):
        module = load_module("clean_runtime", "scripts/ops/clean_runtime.py")
        now_epoch = 1_000_000

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            stale_browser = root / "external" / "browser" / "tmp" / "clone-a"
            stale_repos = root / "external" / "repos" / "stale-repo"
            legacy_link = root / "legacy" / "repos" / "stale-repo"
            write_file(stale_browser / "Default" / "Preferences")
            write_file(stale_repos / "notesctl")
            write_file(legacy_link / "notesctl")
            set_mtime(stale_browser, now_epoch - (25 * 3600))
            set_mtime(stale_repos, now_epoch - (100 * 3600))
            set_mtime(legacy_link, now_epoch - (100 * 3600))

            argv = [
                "clean_runtime.py",
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
                str(root / "external" / "browser" / "chrome-user-data"),
                "--browser-temp-root",
                str(root / "external" / "browser" / "tmp"),
                "--retention-hours",
                "72",
                "--browser-retention-hours",
                "24",
                "--max-external-bytes",
                "1024",
                "--now-epoch",
                str(now_epoch),
            ]

            with mock.patch("sys.argv", [*argv, "--dry-run"]):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    exit_code = module.main()
            self.assertEqual(exit_code, 0)
            self.assertIn("mode=dry-run", buffer.getvalue())
            self.assertTrue(stale_browser.exists())
            self.assertTrue(stale_repos.exists())

            with mock.patch("sys.argv", [*argv, "--apply", "--quiet-auto"]):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    exit_code = module.main()
            self.assertEqual(exit_code, 0)
            self.assertEqual(buffer.getvalue(), "")
            self.assertFalse(stale_browser.exists())
            self.assertFalse(stale_repos.exists())
            self.assertFalse(legacy_link.exists())
