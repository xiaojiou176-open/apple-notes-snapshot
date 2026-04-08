import importlib.util
import os
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path


def load_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "ops" / "runtime_hygiene.py"
    spec = importlib.util.spec_from_file_location("runtime_hygiene", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_file(path: Path, size: int = 8):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def set_mtime(path: Path, epoch: int):
    os.utime(path, (epoch, epoch), follow_symlinks=False)


class RuntimeHygieneUnitTests(unittest.TestCase):
    def test_repo_local_entries_include_runtime_cache_roots_and_legacy_residue(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            write_file(repo_root / ".runtime-cache" / "pytest" / "state")
            write_file(repo_root / ".runtime-cache" / "coverage" / ".coverage")
            write_file(repo_root / ".runtime-cache" / "pycache" / "module.pyc")
            write_file(repo_root / ".runtime-cache" / "browser-proof" / "proof.png")
            write_file(repo_root / ".runtime-cache" / "phase1" / "rollback" / "pre-cutover.bundle")
            write_file(repo_root / ".runtime-cache" / "phase1-history-rebuild" / "rollback.bundle")
            write_file(repo_root / ".runtime-cache" / "mcp-registry-lane" / "out" / "artifact.mcpb")
            write_file(repo_root / ".pytest_cache" / "legacy")
            write_file(repo_root / ".coverage")

            entries = module.repo_local_entries(repo_root)
            classes = {entry["class"]: entry for entry in entries}

        self.assertTrue(classes["repo-local-pytest-cache"]["exists"])
        self.assertTrue(classes["repo-local-coverage"]["exists"])
        self.assertTrue(classes["repo-local-pycache"]["exists"])
        self.assertTrue(classes["repo-local-browser-proof"]["exists"])
        self.assertTrue(classes["repo-local-history-rebuild"]["exists"])
        self.assertTrue(classes["repo-local-history-rebuild-rollback"]["exists"])
        self.assertTrue(classes["repo-local-registry-stage"]["exists"])
        self.assertTrue(classes["legacy-pytest-cache"]["exists"])
        self.assertTrue(classes["legacy-coverage"]["exists"])

    def test_current_labels_are_protected_and_recent_entries_can_be_budget_evicted(self):
        module = load_module()
        now_epoch = 1_000_000
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            current_launchd = root / "external" / "launchd" / "local.apple-notes-snapshot"
            budget_runtime = root / "external" / "runtime" / "recent-big"
            write_file(current_launchd / "plist", size=4)
            write_file(budget_runtime / "blob.bin", size=64)
            set_mtime(current_launchd, now_epoch - 999_999)
            set_mtime(budget_runtime, now_epoch)

            report = module.build_report(
                repo_root=str(root / "repo"),
                launchd_root=str(root / "external" / "launchd"),
                runtime_root=str(root / "external" / "runtime"),
                repos_root=str(root / "external" / "repos"),
                legacy_launchd_root=str(root / "legacy" / "launchd"),
                legacy_runtime_root=str(root / "legacy" / "runtime"),
                legacy_repos_root=str(root / "legacy" / "repos"),
                vendor_runtime_root=str(root / "external" / "vendor-runtime"),
                legacy_vendor_runtime_root=str(root / "legacy" / "vendor-runtime"),
                browser_root=str(root / "external" / "browser"),
                browser_user_data_root=str(root / "external" / "browser" / "chrome-user-data"),
                browser_temp_root=str(root / "external" / "browser" / "tmp"),
                active_labels=["local.apple-notes-snapshot"],
                retention_hours=72,
                browser_retention_hours=24,
                max_external_bytes=1,
                include_vendor_runtime=False,
                now_epoch=now_epoch,
            )

        by_path = {entry["path"]: entry for entry in report["external_cache"]["entries"]}
        self.assertEqual(by_path[str(current_launchd)]["action"], "skip_current")
        self.assertEqual(by_path[str(current_launchd)]["reason"], "current_label_protected")
        self.assertEqual(by_path[str(budget_runtime)]["action"], "would_remove")
        self.assertEqual(by_path[str(budget_runtime)]["reason"], "over_external_budget")

    def test_browser_ttl_and_vendor_opt_in_are_distinct(self):
        module = load_module()
        now_epoch = 1_000_000
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            persistent_browser = root / "external" / "browser" / "chrome-user-data"
            stale_browser = root / "external" / "browser" / "tmp" / "clone-a"
            vendor_current = root / "external" / "vendor-runtime" / "current"
            write_file(persistent_browser / "Profile 1" / "Preferences", size=4)
            write_file(stale_browser / "Default" / "Preferences", size=4)
            write_file(vendor_current / "exportnotes.zsh", size=4)
            set_mtime(persistent_browser, now_epoch - (100 * 3600))
            set_mtime(stale_browser, now_epoch - (25 * 3600))
            set_mtime(vendor_current, now_epoch - (80 * 3600))

            default_report = module.build_report(
                repo_root=str(root / "repo"),
                launchd_root=str(root / "external" / "launchd"),
                runtime_root=str(root / "external" / "runtime"),
                repos_root=str(root / "external" / "repos"),
                legacy_launchd_root=str(root / "legacy" / "launchd"),
                legacy_runtime_root=str(root / "legacy" / "runtime"),
                legacy_repos_root=str(root / "legacy" / "repos"),
                vendor_runtime_root=str(root / "external" / "vendor-runtime"),
                legacy_vendor_runtime_root=str(root / "legacy" / "vendor-runtime"),
                browser_root=str(root / "external" / "browser"),
                browser_user_data_root=str(persistent_browser),
                browser_temp_root=str(root / "external" / "browser" / "tmp"),
                active_labels=[],
                retention_hours=72,
                browser_retention_hours=24,
                max_external_bytes=1024,
                include_vendor_runtime=False,
                now_epoch=now_epoch,
            )
            include_vendor_report = module.build_report(
                repo_root=str(root / "repo"),
                launchd_root=str(root / "external" / "launchd"),
                runtime_root=str(root / "external" / "runtime"),
                repos_root=str(root / "external" / "repos"),
                legacy_launchd_root=str(root / "legacy" / "launchd"),
                legacy_runtime_root=str(root / "legacy" / "runtime"),
                legacy_repos_root=str(root / "legacy" / "repos"),
                vendor_runtime_root=str(root / "external" / "vendor-runtime"),
                legacy_vendor_runtime_root=str(root / "legacy" / "vendor-runtime"),
                browser_root=str(root / "external" / "browser"),
                browser_user_data_root=str(persistent_browser),
                browser_temp_root=str(root / "external" / "browser" / "tmp"),
                active_labels=[],
                retention_hours=72,
                browser_retention_hours=24,
                max_external_bytes=1024,
                include_vendor_runtime=True,
                now_epoch=now_epoch,
            )

        browser_entry = next(
            entry for entry in default_report["external_cache"]["entries"] if entry["kind"] == "browser-temp"
        )
        persistent_entry = next(
            entry for entry in default_report["external_cache"]["persistent_entries"] if entry["kind"] == "browser-user-data"
        )
        default_vendor = next(
            entry
            for entry in default_report["conditional_paths"]
            if "/external/" in entry["path"] and entry["path"].endswith("/current")
        )
        included_vendor = next(
            entry
            for entry in include_vendor_report["conditional_paths"]
            if "/external/" in entry["path"] and entry["path"].endswith("/current")
        )

        self.assertTrue(browser_entry["stale"])
        self.assertEqual(browser_entry["action"], "would_remove")
        self.assertEqual(persistent_entry["action"], "skip_protected")
        self.assertEqual(persistent_entry["reason"], "persistent_browser_root_excluded")
        self.assertEqual(default_vendor["reason"], "opt_in_required")
        self.assertEqual(default_vendor["action"], "skip_recent")
        self.assertEqual(included_vendor["action"], "would_remove")

    def test_audit_lines_cleanup_helpers_and_apply_entry_cover_runtime_helpers(self):
        module = load_module()
        now_epoch = 1_000_000
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            stale_repos = root / "external" / "repos" / "stale-repo"
            legacy_link = root / "legacy" / "repos" / "stale-repo"
            write_file(stale_repos / "notesctl")
            write_file(legacy_link / "notesctl")
            set_mtime(stale_repos, now_epoch - (100 * 3600))
            set_mtime(legacy_link, now_epoch - (100 * 3600))

            report = module.build_report(
                repo_root=str(repo_root),
                launchd_root=str(root / "external" / "launchd"),
                runtime_root=str(root / "external" / "runtime"),
                repos_root=str(root / "external" / "repos"),
                legacy_launchd_root=str(root / "legacy" / "launchd"),
                legacy_runtime_root=str(root / "legacy" / "runtime"),
                legacy_repos_root=str(root / "legacy" / "repos"),
                vendor_runtime_root=str(root / "external" / "vendor-runtime"),
                legacy_vendor_runtime_root=str(root / "legacy" / "vendor-runtime"),
                browser_root=str(root / "external" / "browser"),
                browser_user_data_root=str(root / "external" / "browser" / "chrome-user-data"),
                browser_temp_root=str(root / "external" / "browser" / "tmp"),
                active_labels=[],
                retention_hours=72,
                browser_retention_hours=24,
                max_external_bytes=1024,
                include_vendor_runtime=False,
                now_epoch=now_epoch,
            )

            lines = module.audit_lines(report)
            self.assertEqual(lines[0], "Apple Notes Snapshot runtime-audit")
            self.assertIn("external_cache_roots:", lines)

            cleanup_candidates = module.cleanup_entries(report, include_vendor_runtime=False)
            repo_entry = next(entry for entry in cleanup_candidates if entry["path"] == str(stale_repos))
            self.assertIn("class=external-repo-copy", module.cleanup_line(repo_entry))
            self.assertTrue(module.remove_path(stale_repos))
            write_file(stale_repos / "notesctl")
            removed = module.apply_entry(repo_entry, str(root / "legacy" / "repos"))

        self.assertGreaterEqual(removed, 1)
        self.assertFalse(stale_repos.exists())

    def test_audit_lines_and_cleanup_helpers_render_expected_contract(self):
        module = load_module()
        report = {
            "repo_root": "/tmp/repo",
            "retention_hours": 72,
            "browser_retention_hours": 24,
            "external_cache_max_bytes": 100,
            "current_labels": ["local.apple-notes-snapshot"],
            "repo_local": [
                {
                    "class": "repo-local-pycache",
                    "path": "/tmp/repo/.runtime-cache/pycache",
                    "exists": True,
                    "bytes": 12,
                    "mtime": "2026-04-04 12:00:00 PDT",
                }
            ],
            "external_cache": {
                "roots": {
                    "launchd_root": "/tmp/cache/launchd",
                    "runtime_root": "/tmp/cache/runtime",
                    "repos_root": "/tmp/cache/repos",
                    "browser_root": "/tmp/cache/browser",
                    "browser_user_data_root": "/tmp/cache/browser/chrome-user-data",
                    "browser_temp_root": "/tmp/cache/browser/tmp",
                    "vendor_runtime_root": "/tmp/cache/vendor-runtime",
                },
                "legacy_roots": {
                    "launchd_root": "/tmp/legacy/launchd",
                    "runtime_root": "/tmp/legacy/runtime",
                    "repos_root": "/tmp/legacy/repos",
                    "vendor_runtime_root": "/tmp/legacy/vendor-runtime",
                },
                "total_bytes_before_cleanup": 12,
                "entries": [
                    {
                        "class": "external-runtime",
                        "kind": "runtime",
                        "label": "old-runtime",
                        "path": "/tmp/cache/runtime/old-runtime",
                        "bytes": 4,
                        "mtime": "2026-04-04 10:00:00 PDT",
                        "is_current": False,
                        "stale": True,
                        "reason": "older_than_retention_window",
                        "action": "would_remove",
                    }
                ],
                "legacy_entries": [],
                "persistent_entries": [
                    {
                        "class": "external-browser-user-data",
                        "kind": "browser-user-data",
                        "path": "/tmp/cache/browser/chrome-user-data",
                        "bytes": 8,
                        "mtime": "2026-04-04 09:30:00 PDT",
                        "reason": "persistent_browser_root_excluded",
                        "action": "skip_protected",
                    }
                ],
            },
            "conditional_paths": [
                {
                    "class": "external-vendor-runtime",
                    "label": "current",
                    "path": "/tmp/cache/vendor-runtime/current",
                    "bytes": 8,
                    "mtime": "2026-04-04 09:00:00 PDT",
                    "root_set": "current",
                    "reason": "opt_in_required",
                    "action": "skip_recent",
                }
            ],
            "cleanup_contract": {
                "repo_local_cleanup_available": True,
                "external_cache_cleanup_available": True,
                "persistent_browser_root_cleanup_available": False,
                "docker_cleanup_available": False,
                "var_folders_cleanup_available": False,
                "shared_tool_cleanup_available": False,
            },
        }

        rendered = "\n".join(module.audit_lines(report))
        self.assertIn("Apple Notes Snapshot runtime-audit", rendered)
        self.assertIn("external_cache_roots:", rendered)
        self.assertIn("persistent_external_entries:", rendered)
        self.assertIn("cleanup_contract:", rendered)

        without_vendor = module.cleanup_entries(report, include_vendor_runtime=False)
        with_vendor = module.cleanup_entries(report, include_vendor_runtime=True)
        self.assertEqual(len(without_vendor), 1)
        self.assertEqual(len(with_vendor), 2)
        self.assertIn("action=would_remove", module.cleanup_line(without_vendor[0]))

    def test_apply_entry_removes_current_repo_copy_and_legacy_shadow(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            current_repo_copy = root / "cache" / "repos" / "old-copy"
            legacy_repos_root = root / "legacy" / "repos"
            legacy_repo_copy = legacy_repos_root / "old-copy"
            write_file(current_repo_copy / "marker.txt")
            write_file(legacy_repo_copy / "marker.txt")

            removed = module.apply_entry(
                {
                    "path": str(current_repo_copy),
                    "kind": "repos",
                    "label": "old-copy",
                    "root_set": "current",
                },
                str(legacy_repos_root),
            )

        self.assertEqual(removed, 2)
        self.assertFalse(current_repo_copy.exists())
        self.assertFalse(legacy_repo_copy.exists())

    def test_path_exists_and_size_bytes_handle_files_and_missing_paths(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            file_path = root / "payload.txt"
            file_path.write_bytes(b"payload")
            missing = root / "missing"

            self.assertTrue(module.path_exists(file_path))
            self.assertFalse(module.path_exists(missing))
            self.assertEqual(module.size_bytes(file_path), 7)
            self.assertEqual(module.size_bytes(missing), 0)

    def test_helper_edge_cases_cover_symlink_and_missing_root_scan(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target = root / "target.txt"
            target.write_text("payload\n", encoding="utf-8")
            link = root / "link.txt"
            link.symlink_to(target)

            self.assertEqual(module.size_bytes(link), link.lstat().st_size)
            self.assertEqual(module.format_mtime(None), "")
            self.assertEqual(module.current_labels(["", "a", "a", "b"]), ["a", "b"])

            missing_entries = module.scan_root(
                kind="runtime",
                class_name="external-runtime",
                root=root / "missing",
                active_labels=[],
                cutoff_epoch=0,
                root_set="current",
            )
            self.assertEqual(missing_entries[0]["action"], "missing")

            with mock.patch.object(Path, "iterdir", side_effect=OSError("boom")):
                errored_entries = module.scan_root(
                    kind="runtime",
                    class_name="external-runtime",
                    root=root,
                    active_labels=[],
                    cutoff_epoch=0,
                    root_set="current",
                )
            self.assertEqual(errored_entries[0]["reason"], "root_unreadable")

    def test_remove_path_handles_missing_file_directory_and_symlink(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            file_path = root / "payload.txt"
            dir_path = root / "dir"
            missing = root / "missing"
            symlink_path = root / "payload-link"

            file_path.write_text("payload\n", encoding="utf-8")
            dir_path.mkdir()
            symlink_path.symlink_to(file_path)

            self.assertFalse(module.remove_path(missing))
            self.assertTrue(module.remove_path(symlink_path))
            self.assertTrue(module.remove_path(file_path))
            self.assertTrue(module.remove_path(dir_path))

    def test_mark_external_budget_stops_once_total_is_under_limit(self):
        module = load_module()
        entries = [
            {"action": "skip_recent", "bytes": 5, "mtime_epoch": 10, "is_current": False},
            {"action": "skip_recent", "bytes": 5, "mtime_epoch": 20, "is_current": False, "budget_eligible": False},
        ]

        marked, total = module.mark_external_budget(entries, max_external_bytes=5)
        self.assertEqual(total, 10)
        self.assertEqual(marked[0]["action"], "would_remove")
        self.assertEqual(marked[1]["action"], "skip_recent")


if __name__ == "__main__":
    unittest.main()
