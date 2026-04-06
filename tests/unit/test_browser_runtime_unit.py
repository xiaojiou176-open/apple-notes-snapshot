import importlib.util
import os
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path


def load_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "ops" / "browser_runtime.py"
    spec = importlib.util.spec_from_file_location("browser_runtime", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BrowserRuntimeUnitTests(unittest.TestCase):
    def test_defaults_and_path_helpers(self):
        module = load_module()
        with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": "/tmp/xdg-cache"}, clear=True):
            default_root = module.default_external_cache_root()
            settings = module.default_settings_from_env()
        self.assertEqual(default_root, "/tmp/xdg-cache/apple-notes-snapshot")
        self.assertEqual(module.default_browser_root("/tmp/xdg-cache/apple-notes-snapshot"), "/tmp/xdg-cache/apple-notes-snapshot/browser")
        self.assertEqual(settings["browser_root"], "/tmp/xdg-cache/apple-notes-snapshot/browser")
        self.assertEqual(settings["chrome_profile_dir"], "Profile 1")

    def test_local_state_helpers_and_profile_lookup(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = {
                "profile": {
                    "info_cache": {
                        "Profile 24": {"name": "apple-notes-snapshot"},
                    }
                }
            }
            module.write_local_state(root / "Local State", payload)
            loaded = module.load_local_state(root / "Local State")
            self.assertEqual(loaded["profile"]["info_cache"]["Profile 24"]["name"], "apple-notes-snapshot")
            (root / "Profile 24").mkdir()
            self.assertEqual(module.find_profile_dir_by_display_name(root, "apple-notes-snapshot"), "Profile 24")
            self.assertIsNone(module.find_profile_dir_by_display_name(root, "missing"))
            (root / "Broken Local State").write_text("{not-json", encoding="utf-8")
            self.assertEqual(module.load_local_state(root / "Broken Local State"), {})

    def test_normalize_local_state_and_lock_cleanup(self):
        module = load_module()
        local_state = {
            "profile": {
                "info_cache": {
                    "Profile 24": {"name": "apple-notes-snapshot", "gaia_name": "Lei"},
                    "Profile 25": {"name": "other"},
                }
            }
        }
        normalized = module.normalize_local_state_for_target(local_state, "Profile 24", "Profile 1", "apple-notes-snapshot")
        self.assertIn("Profile 1", normalized["profile"]["info_cache"])
        self.assertNotIn("Profile 24", normalized["profile"]["info_cache"])
        self.assertEqual(normalized["profile"]["last_used"], "Profile 1")

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "Profile 1").mkdir(parents=True)
            (root / "SingletonLock").write_text("lock", encoding="utf-8")
            (root / "Profile 1" / "DevToolsActivePort").write_text("1234", encoding="utf-8")
            removed = module.remove_lock_files(root)
            self.assertEqual(len(removed), 2)
            self.assertFalse((root / "SingletonLock").exists())
            self.assertFalse((root / "Profile 1" / "DevToolsActivePort").exists())

    def test_process_and_cdp_helpers(self):
        module = load_module()
        self.assertTrue(module.process_uses_user_data_dir("Google Chrome --user-data-dir=/tmp/root", "/tmp/root"))
        self.assertFalse(module.process_uses_user_data_dir("Google Chrome --user-data-dir=/tmp/other", "/tmp/root"))
        self.assertEqual(module.cdp_url("127.0.0.1", 9337), "http://127.0.0.1:9337")

        with mock.patch.object(module, "list_chrome_processes", return_value=[{"pid": 1, "args": "Google Chrome --user-data-dir=/tmp/source"}]):
            quiet, processes = module.default_root_is_quiet("/tmp/source")
        self.assertFalse(quiet)
        self.assertEqual(processes[0]["pid"], 1)

        with mock.patch.object(module, "probe_cdp", side_effect=[None, {"Browser": "Chrome/146"}]), mock.patch.object(
            module.time, "sleep"
        ):
            payload = module.wait_for_cdp("127.0.0.1", 9337, timeout_sec=1)
        self.assertEqual(payload["Browser"], "Chrome/146")

    def test_launch_command_and_attach_payload(self):
        module = load_module()
        settings = {
            "chrome_channel": "chrome",
            "chrome_user_data_dir": "/tmp/browser/chrome-user-data",
            "chrome_profile_dir": "Profile 1",
            "chrome_cdp_host": "127.0.0.1",
            "chrome_cdp_port": 9337,
        }
        with mock.patch.object(module, "chrome_binary_for_channel", return_value="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
            command = module.launch_command(settings)
        self.assertIn("--profile-directory=Profile 1", command)
        attach = module.build_attach_payload(settings)
        self.assertEqual(attach["playwright"]["connectOverCDP"]["endpointURL"], "http://127.0.0.1:9337")

    def test_chrome_binary_for_channel_handles_unsupported_and_missing_binary(self):
        module = load_module()
        self.assertIsNone(module.chrome_binary_for_channel("chromium"))
        with mock.patch.object(module.Path, "exists", return_value=False):
            self.assertIsNone(module.chrome_binary_for_channel("chrome"))


if __name__ == "__main__":
    unittest.main()
