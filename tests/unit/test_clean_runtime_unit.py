import contextlib
import importlib.util
import io
import sys
import unittest
import unittest.mock as mock
from pathlib import Path


def load_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "ops" / "clean_runtime.py"
    spec = importlib.util.spec_from_file_location("clean_runtime", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CleanRuntimeUnitTests(unittest.TestCase):
    def test_parse_args_reads_cleanup_flags(self):
        module = load_module()
        argv = [
            "clean_runtime.py",
            "--dry-run",
            "--retention-hours",
            "48",
            "--browser-retention-hours",
            "12",
            "--max-external-bytes",
            "2048",
            "--include-vendor-runtime",
            "--quiet-auto",
            "--repo-root",
            "/tmp/repo",
            "--launchd-root",
            "/tmp/cache/launchd",
            "--runtime-root",
            "/tmp/cache/runtime",
            "--repos-root",
            "/tmp/cache/repos",
            "--legacy-launchd-root",
            "/tmp/legacy/launchd",
            "--legacy-runtime-root",
            "/tmp/legacy/runtime",
            "--legacy-repos-root",
            "/tmp/legacy/repos",
            "--vendor-runtime-root",
            "/tmp/cache/vendor-runtime",
            "--legacy-vendor-runtime-root",
            "/tmp/legacy/vendor-runtime",
            "--browser-root",
            "/tmp/cache/browser",
            "--browser-user-data-root",
            "/tmp/cache/browser/chrome-user-data",
            "--browser-temp-root",
            "/tmp/cache/browser/tmp",
            "--current-label",
            "local.apple-notes-snapshot",
            "--now-epoch",
            "123",
        ]
        with mock.patch.object(sys, "argv", argv):
            args = module.parse_args()

        self.assertTrue(args.dry_run)
        self.assertEqual(args.retention_hours, 48)
        self.assertEqual(args.browser_retention_hours, 12)
        self.assertEqual(args.max_external_bytes, 2048)
        self.assertTrue(args.include_vendor_runtime)
        self.assertTrue(args.quiet_auto)
        self.assertEqual(args.current_label, ["local.apple-notes-snapshot"])
        self.assertEqual(args.now_epoch, 123)

    def test_main_dry_run_reports_counts(self):
        module = load_module()
        report = {
            "retention_hours": 72,
            "browser_retention_hours": 24,
            "external_cache_max_bytes": 100,
            "current_labels": ["local.apple-notes-snapshot"],
            "external_cache": {"legacy_roots": {"repos_root": "/tmp/legacy/repos"}},
            "conditional_paths": [],
        }
        entries = [
            {"action": "missing", "class": "missing"},
            {"action": "would_remove", "class": "remove"},
            {"action": "skip_recent", "class": "skip"},
        ]

        with mock.patch.object(
            module,
            "parse_args",
            return_value=mock.Mock(
                dry_run=True,
                apply=False,
                retention_hours=72,
                browser_retention_hours=24,
                max_external_bytes=100,
                include_vendor_runtime=False,
                quiet_auto=False,
                repo_root="/tmp/repo",
                launchd_root="/tmp/cache/launchd",
                runtime_root="/tmp/cache/runtime",
                repos_root="/tmp/cache/repos",
                legacy_launchd_root="/tmp/legacy/launchd",
                legacy_runtime_root="/tmp/legacy/runtime",
                legacy_repos_root="/tmp/legacy/repos",
                vendor_runtime_root="/tmp/cache/vendor-runtime",
                legacy_vendor_runtime_root="/tmp/legacy/vendor-runtime",
                browser_root="/tmp/cache/browser",
                browser_user_data_root="/tmp/cache/browser/chrome-user-data",
                browser_temp_root="/tmp/cache/browser/tmp",
                current_label=["local.apple-notes-snapshot"],
                now_epoch=123,
            ),
        ), mock.patch.object(module, "build_report", return_value=report), mock.patch.object(
            module, "cleanup_entries", return_value=entries
        ), mock.patch.object(module, "cleanup_line", side_effect=lambda entry: f"line:{entry['class']}"), mock.patch.object(
            module, "apply_entry", return_value=1
        ) as apply_entry:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = module.main()

        self.assertEqual(exit_code, 0)
        output = buffer.getvalue()
        self.assertIn("[clean-runtime] maintainer-only external cleanup lane", output)
        self.assertIn("clean-runtime done (mode=dry-run, removed=0, skipped=2, missing=1)", output)
        apply_entry.assert_not_called()

    def test_main_apply_quiet_auto_suppresses_output(self):
        module = load_module()
        report = {
            "retention_hours": 72,
            "browser_retention_hours": 24,
            "external_cache_max_bytes": 100,
            "current_labels": ["local.apple-notes-snapshot"],
            "external_cache": {"legacy_roots": {"repos_root": "/tmp/legacy/repos"}},
            "conditional_paths": [],
        }
        entries = [{"action": "would_remove", "class": "remove", "path": "/tmp/path"}]

        with mock.patch.object(
            module,
            "parse_args",
            return_value=mock.Mock(
                dry_run=False,
                apply=True,
                retention_hours=72,
                browser_retention_hours=24,
                max_external_bytes=100,
                include_vendor_runtime=False,
                quiet_auto=True,
                repo_root="/tmp/repo",
                launchd_root="/tmp/cache/launchd",
                runtime_root="/tmp/cache/runtime",
                repos_root="/tmp/cache/repos",
                legacy_launchd_root="/tmp/legacy/launchd",
                legacy_runtime_root="/tmp/legacy/runtime",
                legacy_repos_root="/tmp/legacy/repos",
                vendor_runtime_root="/tmp/cache/vendor-runtime",
                legacy_vendor_runtime_root="/tmp/legacy/vendor-runtime",
                browser_root="/tmp/cache/browser",
                browser_user_data_root="/tmp/cache/browser/chrome-user-data",
                browser_temp_root="/tmp/cache/browser/tmp",
                current_label=["local.apple-notes-snapshot"],
                now_epoch=123,
            ),
        ), mock.patch.object(module, "build_report", return_value=report), mock.patch.object(
            module, "cleanup_entries", return_value=entries
        ), mock.patch.object(module, "apply_entry", return_value=2) as apply_entry:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = module.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue(), "")
        apply_entry.assert_called_once_with(entries[0], "/tmp/legacy/repos")
