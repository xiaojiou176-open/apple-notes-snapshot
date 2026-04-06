import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path


def load_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "ops" / "browser_open.py"
    spec = importlib.util.spec_from_file_location("browser_open", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BrowserOpenUnitTests(unittest.TestCase):
    def test_parse_args_reads_json_flag(self):
        module = load_module()
        with mock.patch.object(sys, "argv", ["browser_open.py", "--json"]):
            args = module.parse_args()
        self.assertTrue(args.json)

    def test_fail_fast_when_provider_or_isolated_root_is_invalid(self):
        module = load_module()
        env = {
            "NOTES_SNAPSHOT_BROWSER_PROVIDER": "chromium",
            "NOTES_SNAPSHOT_CHROME_USER_DATA_DIR": "/tmp/does-not-exist-apple-notes-snapshot-browser",
            "NOTES_SNAPSHOT_CHROME_PROFILE_DIR": "Profile 1",
            "NOTES_SNAPSHOT_CHROME_CDP_HOST": "127.0.0.1",
            "NOTES_SNAPSHOT_CHROME_CDP_PORT": "9337",
        }
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
            module, "chrome_binary_for_channel", return_value=None
        ), mock.patch.object(
            module, "list_chrome_processes", return_value=[]
        ), mock.patch.object(
            module, "probe_cdp", return_value=None
        ), mock.patch.object(
            module, "tcp_listener_present", return_value=False
        ), mock.patch.object(
            module, "parse_args", return_value=mock.Mock(json=False)
        ):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = module.main()

        self.assertEqual(exit_code, 1)
        output = buffer.getvalue()
        self.assertIn("Unsupported browser provider", output)
        self.assertIn("Chrome binary for channel 'chrome' was not found.", output)
        self.assertIn("Isolated Chrome user data dir does not exist", output)
        self.assertIn("Isolated Chrome profile dir does not exist", output)

    def test_existing_repo_owned_instance_returns_attach_info_without_launch(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            user_data_dir = Path(tmpdir) / "chrome-user-data"
            (user_data_dir / "Profile 1").mkdir(parents=True)
            env = {
                "NOTES_SNAPSHOT_BROWSER_PROVIDER": "chrome",
                "NOTES_SNAPSHOT_CHROME_USER_DATA_DIR": str(user_data_dir),
                "NOTES_SNAPSHOT_CHROME_PROFILE_DIR": "Profile 1",
                "NOTES_SNAPSHOT_CHROME_CDP_HOST": "127.0.0.1",
                "NOTES_SNAPSHOT_CHROME_CDP_PORT": "9337",
            }
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                module, "chrome_binary_for_channel", return_value="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            ), mock.patch.object(
                module, "list_chrome_processes", return_value=[{"pid": 10, "args": f"Google Chrome --user-data-dir={user_data_dir}"}]
            ), mock.patch.object(
                module, "probe_cdp", return_value={"Browser": "Chrome/136"}
            ), mock.patch.object(
                module.subprocess, "Popen"
            ) as popen_mock, mock.patch.object(
                module, "tcp_listener_present", return_value=True
            ), mock.patch.object(
                module, "parse_args", return_value=mock.Mock(json=False)
            ):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    exit_code = module.main()

        self.assertEqual(exit_code, 0)
        self.assertIn("status=attach", buffer.getvalue())
        popen_mock.assert_not_called()

    def test_launches_repo_owned_instance_when_not_running(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            user_data_dir = Path(tmpdir) / "chrome-user-data"
            (user_data_dir / "Profile 1").mkdir(parents=True)
            env = {
                "NOTES_SNAPSHOT_BROWSER_PROVIDER": "chrome",
                "NOTES_SNAPSHOT_CHROME_USER_DATA_DIR": str(user_data_dir),
                "NOTES_SNAPSHOT_CHROME_PROFILE_DIR": "Profile 1",
                "NOTES_SNAPSHOT_CHROME_CDP_HOST": "127.0.0.1",
                "NOTES_SNAPSHOT_CHROME_CDP_PORT": "9337",
            }
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                module, "chrome_binary_for_channel", return_value="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            ), mock.patch.object(
                module, "list_chrome_processes", return_value=[]
            ), mock.patch.object(
                module, "probe_cdp", return_value=None
            ), mock.patch.object(
                module, "tcp_listener_present", return_value=False
            ), mock.patch.object(
                module, "wait_for_cdp", return_value={"Browser": "Chrome/136"}
            ), mock.patch.object(
                module.subprocess, "Popen"
            ) as popen_mock, mock.patch.object(
                module, "parse_args", return_value=mock.Mock(json=False)
            ):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    exit_code = module.main()

        self.assertEqual(exit_code, 0)
        self.assertIn("status=launched", buffer.getvalue())
        popen_mock.assert_called_once()

    def test_fails_when_cdp_port_is_owned_by_foreign_instance(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            user_data_dir = Path(tmpdir) / "chrome-user-data"
            (user_data_dir / "Profile 1").mkdir(parents=True)
            env = {
                "NOTES_SNAPSHOT_BROWSER_PROVIDER": "chrome",
                "NOTES_SNAPSHOT_CHROME_USER_DATA_DIR": str(user_data_dir),
                "NOTES_SNAPSHOT_CHROME_PROFILE_DIR": "Profile 1",
            }
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                module, "chrome_binary_for_channel", return_value="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            ), mock.patch.object(
                module, "list_chrome_processes", return_value=[{"pid": 11, "args": "Google Chrome --user-data-dir=/tmp/other"}]
            ), mock.patch.object(
                module, "probe_cdp", return_value={"Browser": "Chrome/136"}
            ), mock.patch.object(
                module, "tcp_listener_present", return_value=True
            ), mock.patch.object(
                module, "parse_args", return_value=mock.Mock(json=False)
            ):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    exit_code = module.main()

        self.assertEqual(exit_code, 1)
        self.assertIn("CDP port conflict", buffer.getvalue())

    def test_fails_when_repo_process_exists_but_cdp_is_unavailable(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            user_data_dir = Path(tmpdir) / "chrome-user-data"
            (user_data_dir / "Profile 1").mkdir(parents=True)
            env = {
                "NOTES_SNAPSHOT_BROWSER_PROVIDER": "chrome",
                "NOTES_SNAPSHOT_CHROME_USER_DATA_DIR": str(user_data_dir),
                "NOTES_SNAPSHOT_CHROME_PROFILE_DIR": "Profile 1",
            }
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                module, "chrome_binary_for_channel", return_value="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            ), mock.patch.object(
                module, "list_chrome_processes", return_value=[{"pid": 77, "args": f"Google Chrome --user-data-dir={user_data_dir}"}]
            ), mock.patch.object(
                module, "probe_cdp", return_value=None
            ), mock.patch.object(
                module, "tcp_listener_present", return_value=True
            ), mock.patch.object(
                module, "parse_args", return_value=mock.Mock(json=True)
            ):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    exit_code = module.main()

        self.assertEqual(exit_code, 1)
        self.assertIn("configured CDP endpoint is unavailable", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
