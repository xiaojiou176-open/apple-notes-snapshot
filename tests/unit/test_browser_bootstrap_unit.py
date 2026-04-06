import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path


def load_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "ops" / "browser_bootstrap.py"
    spec = importlib.util.spec_from_file_location("browser_bootstrap", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BrowserBootstrapUnitTests(unittest.TestCase):
    def test_parse_args_reads_json_flag(self):
        module = load_module()
        with mock.patch.object(sys, "argv", ["browser_bootstrap.py", "--json"]):
            args = module.parse_args()
        self.assertTrue(args.json)

    def test_bootstrap_copies_profile_24_into_profile_1_and_rewrites_local_state(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            source_root = tmp / "source"
            target_root = tmp / "browser" / "chrome-user-data"
            profile_24 = source_root / "Profile 24"
            profile_24.mkdir(parents=True)
            (profile_24 / "Cookies").write_text("cookie-db", encoding="utf-8")
            (profile_24 / "SingletonLock").write_text("lock", encoding="utf-8")
            (source_root / "Local State").write_text(
                json.dumps(
                    {
                        "profile": {
                            "info_cache": {
                                "Profile 24": {"name": "apple-notes-snapshot"},
                                "Profile 25": {"name": "other"},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            env = {
                "NOTES_SNAPSHOT_BROWSER_PROVIDER": "chrome",
                "NOTES_SNAPSHOT_BROWSER_ROOT": str(tmp / "browser"),
                "NOTES_SNAPSHOT_CHROME_USER_DATA_DIR": str(target_root),
                "NOTES_SNAPSHOT_CHROME_PROFILE_NAME": "apple-notes-snapshot",
                "NOTES_SNAPSHOT_CHROME_PROFILE_DIR": "Profile 1",
            }
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                module, "default_root_is_quiet", return_value=(True, [])
            ), mock.patch.object(
                module, "default_settings_from_env", return_value={**module.default_settings_from_env(), **env, "default_source_user_data_dir": str(source_root)}
            ), mock.patch.object(
                module, "parse_args", return_value=mock.Mock(json=False)
            ):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    exit_code = module.main()

                rewritten = json.loads((target_root / "Local State").read_text(encoding="utf-8"))
                cookies_exists = (target_root / "Profile 1" / "Cookies").exists()
                singleton_exists = (target_root / "Profile 1" / "SingletonLock").exists()

        self.assertEqual(exit_code, 0)
        self.assertIn("Profile 1", rewritten["profile"]["info_cache"])
        self.assertNotIn("Profile 24", rewritten["profile"]["info_cache"])
        self.assertEqual(rewritten["profile"]["info_cache"]["Profile 1"]["name"], "apple-notes-snapshot")
        self.assertTrue(cookies_exists)
        self.assertFalse(singleton_exists)

    def test_bootstrap_refuses_when_foreign_chrome_is_running(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            source_root = Path(tmpdir) / "source"
            source_root.mkdir(parents=True)
            (source_root / "Local State").write_text("{}", encoding="utf-8")
            env = {
                "NOTES_SNAPSHOT_BROWSER_PROVIDER": "chrome",
                "NOTES_SNAPSHOT_CHROME_USER_DATA_DIR": str(Path(tmpdir) / "target"),
            }
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                module, "default_root_is_quiet", return_value=(False, [{"pid": 123, "args": "Google Chrome"}])
            ), mock.patch.object(
                module, "default_settings_from_env", return_value={**module.default_settings_from_env(), **env, "default_source_user_data_dir": str(source_root)}
            ), mock.patch.object(
                module, "parse_args", return_value=mock.Mock(json=False)
            ):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    exit_code = module.main()

        self.assertEqual(exit_code, 1)
        self.assertIn("status=invalid", buffer.getvalue())
        self.assertIn("Default Chrome root is not quiet", buffer.getvalue())

    def test_bootstrap_json_success_payload(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            source_root = tmp / "source"
            target_root = tmp / "browser" / "chrome-user-data"
            profile_24 = source_root / "Profile 24"
            profile_24.mkdir(parents=True)
            (source_root / "Local State").write_text(
                json.dumps({"profile": {"info_cache": {"Profile 24": {"name": "apple-notes-snapshot"}}}}),
                encoding="utf-8",
            )
            env = {
                "NOTES_SNAPSHOT_BROWSER_PROVIDER": "chrome",
                "NOTES_SNAPSHOT_BROWSER_ROOT": str(tmp / "browser"),
                "NOTES_SNAPSHOT_CHROME_USER_DATA_DIR": str(target_root),
                "NOTES_SNAPSHOT_CHROME_PROFILE_NAME": "apple-notes-snapshot",
                "NOTES_SNAPSHOT_CHROME_PROFILE_DIR": "Profile 1",
            }
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                module, "default_root_is_quiet", return_value=(True, [])
            ), mock.patch.object(
                module, "default_settings_from_env", return_value={**module.default_settings_from_env(), **env, "default_source_user_data_dir": str(source_root)}
            ), mock.patch.object(
                module, "parse_args", return_value=mock.Mock(json=True)
            ):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    exit_code = module.main()

        self.assertEqual(exit_code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["target_profile_dir"], "Profile 1")

    def test_bootstrap_reports_missing_source_root_and_bad_provider(self):
        module = load_module()
        env = {
            "NOTES_SNAPSHOT_BROWSER_PROVIDER": "chromium",
            "NOTES_SNAPSHOT_CHROME_USER_DATA_DIR": "/tmp/target-browser-root",
        }
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
            module, "default_root_is_quiet", return_value=(True, [])
        ), mock.patch.object(
            module, "default_settings_from_env", return_value={**module.default_settings_from_env(), **env, "default_source_user_data_dir": "/tmp/missing-source-root"}
        ), mock.patch.object(
            module, "parse_args", return_value=mock.Mock(json=True)
        ):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = module.main()

        self.assertEqual(exit_code, 1)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(any("Unsupported browser provider: chromium" in err for err in payload["errors"]))
        self.assertTrue(any("Default Chrome user data dir was not found" in err for err in payload["errors"]))

    def test_bootstrap_refuses_when_target_root_is_not_empty(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            source_root = tmp / "source"
            source_root.mkdir(parents=True)
            (source_root / "Profile 24").mkdir()
            (source_root / "Local State").write_text(
                json.dumps({"profile": {"info_cache": {"Profile 24": {"name": "apple-notes-snapshot"}}}}),
                encoding="utf-8",
            )
            target_root = tmp / "browser" / "chrome-user-data"
            target_root.mkdir(parents=True)
            (target_root / "marker.txt").write_text("x", encoding="utf-8")
            env = {
                "NOTES_SNAPSHOT_BROWSER_PROVIDER": "chrome",
                "NOTES_SNAPSHOT_BROWSER_ROOT": str(tmp / "browser"),
                "NOTES_SNAPSHOT_CHROME_USER_DATA_DIR": str(target_root),
            }
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                module, "default_root_is_quiet", return_value=(True, [])
            ), mock.patch.object(
                module, "default_settings_from_env", return_value={**module.default_settings_from_env(), **env, "default_source_user_data_dir": str(source_root)}
            ), mock.patch.object(
                module, "parse_args", return_value=mock.Mock(json=True)
            ):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    exit_code = module.main()
        self.assertEqual(exit_code, 1)
        rendered = json.loads(buffer.getvalue())
        self.assertTrue(any("not empty" in err for err in rendered["errors"]))

    def test_bootstrap_reports_copy_failure_cleanly(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            source_root = tmp / "source"
            (source_root / "Profile 24").mkdir(parents=True)
            (source_root / "Local State").write_text(
                json.dumps({"profile": {"info_cache": {"Profile 24": {"name": "apple-notes-snapshot"}}}}),
                encoding="utf-8",
            )
            env = {
                "NOTES_SNAPSHOT_BROWSER_PROVIDER": "chrome",
                "NOTES_SNAPSHOT_CHROME_USER_DATA_DIR": str(tmp / "browser" / "chrome-user-data"),
            }
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                module, "default_root_is_quiet", return_value=(True, [])
            ), mock.patch.object(
                module, "default_settings_from_env", return_value={**module.default_settings_from_env(), **env, "default_source_user_data_dir": str(source_root)}
            ), mock.patch.object(
                module, "parse_args", return_value=mock.Mock(json=True)
            ), mock.patch.object(
                module.shutil, "copy2", side_effect=OSError("copy failed")
            ):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    exit_code = module.main()
        self.assertEqual(exit_code, 1)
        self.assertIn("Failed to copy default Chrome Local State", buffer.getvalue())

    def test_bootstrap_json_error_when_local_state_missing(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            source_root = Path(tmpdir) / "source"
            source_root.mkdir(parents=True)
            env = {
                "NOTES_SNAPSHOT_BROWSER_PROVIDER": "chrome",
                "NOTES_SNAPSHOT_CHROME_USER_DATA_DIR": str(Path(tmpdir) / "target"),
            }
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                module, "default_root_is_quiet", return_value=(True, [])
            ), mock.patch.object(
                module, "default_settings_from_env", return_value={**module.default_settings_from_env(), **env, "default_source_user_data_dir": str(source_root)}
            ), mock.patch.object(
                module, "parse_args", return_value=mock.Mock(json=True)
            ):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    exit_code = module.main()

        self.assertEqual(exit_code, 1)
        payload = json.loads(buffer.getvalue())
        self.assertFalse(payload["ok"])
        self.assertTrue(any("Default Chrome Local State is missing" in err for err in payload["errors"]))

    def test_bootstrap_reports_copy_failure(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            source_root = tmp / "source"
            target_root = tmp / "browser" / "chrome-user-data"
            profile_24 = source_root / "Profile 24"
            profile_24.mkdir(parents=True)
            (source_root / "Local State").write_text(
                json.dumps({"profile": {"info_cache": {"Profile 24": {"name": "apple-notes-snapshot"}}}}),
                encoding="utf-8",
            )
            env = {
                "NOTES_SNAPSHOT_BROWSER_PROVIDER": "chrome",
                "NOTES_SNAPSHOT_BROWSER_ROOT": str(tmp / "browser"),
                "NOTES_SNAPSHOT_CHROME_USER_DATA_DIR": str(target_root),
                "NOTES_SNAPSHOT_CHROME_PROFILE_NAME": "apple-notes-snapshot",
                "NOTES_SNAPSHOT_CHROME_PROFILE_DIR": "Profile 1",
            }
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                module, "default_root_is_quiet", return_value=(True, [])
            ), mock.patch.object(
                module, "default_settings_from_env", return_value={**module.default_settings_from_env(), **env, "default_source_user_data_dir": str(source_root)}
            ), mock.patch.object(
                module, "parse_args", return_value=mock.Mock(json=True)
            ), mock.patch.object(
                module.shutil, "copy2", side_effect=OSError("copy failed")
            ):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    exit_code = module.main()

        self.assertEqual(exit_code, 1)
        payload = json.loads(buffer.getvalue())
        self.assertTrue(any("Failed to copy default Chrome Local State" in err for err in payload["errors"]))


if __name__ == "__main__":
    unittest.main()
