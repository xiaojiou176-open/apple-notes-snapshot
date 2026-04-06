import contextlib
import importlib.util
import io
import sys
import unittest
import unittest.mock as mock
from pathlib import Path


def load_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "ops" / "runtime_audit.py"
    spec = importlib.util.spec_from_file_location("runtime_audit", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RuntimeAuditUnitTests(unittest.TestCase):
    def test_parse_args_reads_required_contract_flags(self):
        module = load_module()
        argv = [
            "runtime_audit.py",
            "--json",
            "--retention-hours",
            "48",
            "--browser-retention-hours",
            "12",
            "--max-external-bytes",
            "2048",
            "--include-vendor-runtime",
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

        self.assertTrue(args.json)
        self.assertEqual(args.retention_hours, 48)
        self.assertEqual(args.browser_retention_hours, 12)
        self.assertEqual(args.max_external_bytes, 2048)
        self.assertTrue(args.include_vendor_runtime)
        self.assertEqual(args.current_label, ["local.apple-notes-snapshot"])
        self.assertEqual(args.now_epoch, 123)

    def test_main_prints_json_report(self):
        module = load_module()
        fake_report = {"repo_root": "/tmp/repo", "external_cache": {"entries": []}}

        with mock.patch.object(
            module,
            "parse_args",
            return_value=mock.Mock(
                json=True,
                retention_hours=72,
                browser_retention_hours=24,
                max_external_bytes=100,
                include_vendor_runtime=False,
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
        ), mock.patch.object(module, "build_report", return_value=fake_report):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = module.main()

        self.assertEqual(exit_code, 0)
        self.assertIn('"repo_root": "/tmp/repo"', buffer.getvalue())

    def test_main_prints_text_lines(self):
        module = load_module()
        with mock.patch.object(
            module,
            "parse_args",
            return_value=mock.Mock(
                json=False,
                retention_hours=72,
                browser_retention_hours=24,
                max_external_bytes=100,
                include_vendor_runtime=False,
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
        ), mock.patch.object(module, "build_report", return_value={"repo_root": "/tmp/repo"}), mock.patch.object(
            module, "audit_lines", return_value=["line-one", "line-two"]
        ):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = module.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue().strip().splitlines(), ["line-one", "line-two"])
