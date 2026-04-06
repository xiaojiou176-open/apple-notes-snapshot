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
    module_path = repo_root / "scripts" / "ops" / "browser_contract.py"
    spec = importlib.util.spec_from_file_location("browser_contract", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BrowserContractUnitTests(unittest.TestCase):
    def test_parse_args_reads_json_flag(self):
        module = load_module()
        with mock.patch.object(sys, "argv", ["browser_contract.py", "--json"]):
            args = module.parse_args()
        self.assertTrue(args.json)

    def test_missing_isolated_root_fails_fast(self):
        module = load_module()
        with mock.patch.dict(
            os.environ,
            {"NOTES_SNAPSHOT_CHROME_USER_DATA_DIR": "/tmp/does-not-exist-browser-root"},
            clear=True,
        ), mock.patch.object(
            module, "chrome_binary_for_channel", return_value="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        ):
            payload = module.resolve_contract_from_env()
        self.assertFalse(payload["ok"])
        self.assertTrue(
            any("Chrome user data dir does not exist:" in err for err in payload["errors"])
        )

    def test_resolves_attach_first_contract_for_isolated_profile(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            browser_root = Path(tmpdir) / "browser"
            user_data_dir = browser_root / "chrome-user-data"
            profile_dir = user_data_dir / "Profile 1"
            profile_dir.mkdir(parents=True)
            (user_data_dir / "Local State").write_text(
                json.dumps(
                    {
                        "profile": {
                            "info_cache": {
                                "Profile 1": {"name": "apple-notes-snapshot"},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            env = {
                "NOTES_SNAPSHOT_BROWSER_PROVIDER": "chrome",
                "NOTES_SNAPSHOT_BROWSER_ROOT": str(browser_root),
                "NOTES_SNAPSHOT_CHROME_USER_DATA_DIR": str(user_data_dir),
                "NOTES_SNAPSHOT_CHROME_PROFILE_NAME": "apple-notes-snapshot",
                "NOTES_SNAPSHOT_CHROME_PROFILE_DIR": "Profile 1",
                "NOTES_SNAPSHOT_CHROME_CDP_HOST": "127.0.0.1",
                "NOTES_SNAPSHOT_CHROME_CDP_PORT": "9337",
            }
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                module, "chrome_binary_for_channel", return_value="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            ), mock.patch.object(
                module,
                "browser_launch_command",
                return_value=[
                    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    "--user-data-dir=/tmp/browser/chrome-user-data",
                    "--profile-directory=Profile 1",
                ],
            ), mock.patch.object(
                module, "list_chrome_processes", return_value=[]
            ), mock.patch.object(
                module, "probe_cdp", return_value=None
            ), mock.patch.object(
                module, "tcp_listener_present", return_value=False
            ):
                payload = module.resolve_contract_from_env()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["browser_root"], str(browser_root))
        self.assertEqual(payload["chrome_profile_dir"], "Profile 1")
        self.assertEqual(payload["cdp"]["url"], "http://127.0.0.1:9337")
        self.assertEqual(
            payload["attach"]["playwright"]["connectOverCDP"]["endpointURL"],
            "http://127.0.0.1:9337",
        )
        self.assertIn("--profile-directory=Profile 1", payload["launch"]["command"])

    def test_detects_cdp_port_conflict(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            user_data_dir = Path(tmpdir) / "chrome-user-data"
            (user_data_dir / "Profile 1").mkdir(parents=True)
            (user_data_dir / "Local State").write_text(
                json.dumps({"profile": {"info_cache": {"Profile 1": {"name": "apple-notes-snapshot"}}}}),
                encoding="utf-8",
            )
            env = {
                "NOTES_SNAPSHOT_BROWSER_PROVIDER": "chrome",
                "NOTES_SNAPSHOT_CHROME_USER_DATA_DIR": str(user_data_dir),
                "NOTES_SNAPSHOT_CHROME_PROFILE_DIR": "Profile 1",
                "NOTES_SNAPSHOT_CHROME_PROFILE_NAME": "apple-notes-snapshot",
            }
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                module, "chrome_binary_for_channel", return_value="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            ), mock.patch.object(
                module, "list_chrome_processes", return_value=[{"pid": 10, "args": "Google Chrome --user-data-dir=/tmp/other"}]
            ), mock.patch.object(
                module, "probe_cdp", return_value={"Browser": "Chrome/136"}
            ), mock.patch.object(
                module, "tcp_listener_present", return_value=True
            ):
                payload = module.resolve_contract_from_env()

        self.assertFalse(payload["ok"])
        self.assertTrue(any("CDP endpoint is already live" in err for err in payload["errors"]))

    def test_rejects_invalid_provider_and_missing_binary(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            user_data_dir = Path(tmpdir) / "chrome-user-data"
            user_data_dir.mkdir(parents=True)
            env = {
                "NOTES_SNAPSHOT_BROWSER_PROVIDER": "chromium",
                "NOTES_SNAPSHOT_CHROME_USER_DATA_DIR": str(user_data_dir),
            }
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                module, "chrome_binary_for_channel", return_value=None
            ), mock.patch.object(
                module, "list_chrome_processes", return_value=[]
            ), mock.patch.object(
                module, "probe_cdp", return_value=None
            ), mock.patch.object(
                module, "tcp_listener_present", return_value=False
            ):
                payload = module.resolve_contract_from_env()
        self.assertFalse(payload["ok"])
        self.assertTrue(any("Unsupported browser provider" in err for err in payload["errors"]))
        self.assertTrue(any("Chrome binary for channel" in err for err in payload["errors"]))

    def test_invalid_text_output_prints_errors(self):
        module = load_module()
        payload = {
            "provider": "chrome",
            "browser_root": "/tmp/browser",
            "browser_temp_root": "/tmp/browser/tmp",
            "chrome_user_data_dir": "/tmp/browser/chrome-user-data",
            "chrome_profile_name": "apple-notes-snapshot",
            "chrome_profile_dir": "Profile 1",
            "chrome_profile_dir_by_name": "",
            "chrome_channel": "chrome",
            "chrome_binary": "",
            "cdp": {"host": "127.0.0.1", "port": 9337, "url": "http://127.0.0.1:9337", "running": False, "port_busy": False, "version": {}},
            "attach": {"playwright": {"connectOverCDP": {"endpointURL": "http://127.0.0.1:9337"}}},
            "launch": {"command": []},
            "processes": {"chrome_process_count": 0, "repo_process_count": 0},
            "ok": False,
            "errors": ["Chrome binary for channel 'chrome' was not found."],
        }
        with mock.patch.object(module, "resolve_contract_from_env", return_value=payload), mock.patch.object(
            module, "parse_args", return_value=mock.Mock(json=False)
        ):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = module.main()

        self.assertEqual(exit_code, 1)
        self.assertIn("status=invalid", buffer.getvalue())
        self.assertIn("Chrome binary for channel 'chrome' was not found.", buffer.getvalue())

    def test_main_prints_attach_first_text_output(self):
        module = load_module()
        payload = {
            "provider": "chrome",
            "browser_root": "/tmp/browser",
            "browser_temp_root": "/tmp/browser/tmp",
            "chrome_user_data_dir": "/tmp/browser/chrome-user-data",
            "chrome_profile_name": "apple-notes-snapshot",
            "chrome_profile_dir": "Profile 1",
            "chrome_profile_dir_by_name": "Profile 1",
            "chrome_channel": "chrome",
            "chrome_binary": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "cdp": {"host": "127.0.0.1", "port": 9337, "url": "http://127.0.0.1:9337", "running": False, "version": {}},
            "attach": {"playwright": {"connectOverCDP": {"endpointURL": "http://127.0.0.1:9337"}}},
            "launch": {"command": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--profile-directory=Profile 1"]},
            "processes": {"chrome_process_count": 0, "repo_process_count": 0},
            "ok": True,
            "errors": [],
        }
        with mock.patch.object(module, "resolve_contract_from_env", return_value=payload), mock.patch.object(
            module, "parse_args", return_value=mock.Mock(json=False)
        ):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = module.main()

        self.assertEqual(exit_code, 0)
        output = buffer.getvalue()
        self.assertIn("cdp_url=http://127.0.0.1:9337", output)
        self.assertIn("playwright_connect_over_cdp=", output)
        self.assertNotIn("launchPersistentContext", output)

    def test_main_prints_json_payload(self):
        module = load_module()
        payload = {
            "provider": "chrome",
            "browser_root": "/tmp/browser",
            "browser_temp_root": "/tmp/browser/tmp",
            "chrome_user_data_dir": "/tmp/browser/chrome-user-data",
            "chrome_profile_name": "apple-notes-snapshot",
            "chrome_profile_dir": "Profile 1",
            "chrome_profile_dir_by_name": "Profile 1",
            "chrome_channel": "chrome",
            "chrome_binary": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "cdp": {"host": "127.0.0.1", "port": 9337, "url": "http://127.0.0.1:9337", "running": True, "version": {"Browser": "Chrome/136"}},
            "attach": {"playwright": {"connectOverCDP": {"endpointURL": "http://127.0.0.1:9337"}}},
            "launch": {"command": []},
            "processes": {"chrome_process_count": 1, "repo_process_count": 1},
            "ok": True,
            "errors": [],
        }
        with mock.patch.object(module, "resolve_contract_from_env", return_value=payload), mock.patch.object(
            module, "parse_args", return_value=mock.Mock(json=True)
        ):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = module.main()

        self.assertEqual(exit_code, 0)
        rendered = json.loads(buffer.getvalue())
        self.assertEqual(rendered["chrome_profile_dir"], "Profile 1")
        self.assertEqual(rendered["cdp"]["url"], "http://127.0.0.1:9337")


if __name__ == "__main__":
    unittest.main()
