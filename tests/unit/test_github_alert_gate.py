import importlib.util
import subprocess
import unittest
import unittest.mock
from pathlib import Path


def load_module(module_name: str, relative_path: str):
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GithubAlertGateTests(unittest.TestCase):
    def test_detect_repo_parses_github_ssh_remote(self):
        mod = load_module("github_alert_gate", "scripts/checks/github_alert_gate.py")

        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="git@github.com:xiaojiou176-open/apple-notes-snapshot.git\n",
            stderr="",
        )
        with unittest.mock.patch.object(mod, "run_command", return_value=completed):
            self.assertEqual(mod.detect_repo(), "xiaojiou176-open/apple-notes-snapshot")

    def test_detect_code_ref_prefers_github_pull_ref(self):
        mod = load_module("github_alert_gate", "scripts/checks/github_alert_gate.py")

        env = {
            "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_REF": "refs/pull/5/merge",
        }
        with unittest.mock.patch.dict(mod.os.environ, env, clear=True):
            self.assertEqual(mod.detect_code_ref(), "refs/pull/5/merge")

    def test_main_fails_when_alerts_exist(self):
        mod = load_module("github_alert_gate", "scripts/checks/github_alert_gate.py")

        with unittest.mock.patch.object(mod, "detect_repo", return_value="xiaojiou176-open/apple-notes-snapshot"), \
            unittest.mock.patch.object(mod, "detect_code_ref", return_value="refs/heads/main"), \
            unittest.mock.patch.object(mod, "list_open_code_alerts", return_value=[{"rule": {"id": "demo-rule"}, "state": "open", "html_url": "https://example.com/code"}]), \
            unittest.mock.patch.object(mod, "list_open_secret_alerts", return_value=[]):
            self.assertEqual(mod.main(), 1)

    def test_main_passes_when_no_alerts_exist(self):
        mod = load_module("github_alert_gate", "scripts/checks/github_alert_gate.py")

        with unittest.mock.patch.object(mod, "detect_repo", return_value="xiaojiou176-open/apple-notes-snapshot"), \
            unittest.mock.patch.object(mod, "detect_code_ref", return_value="refs/heads/main"), \
            unittest.mock.patch.object(mod, "list_open_code_alerts", return_value=[]), \
            unittest.mock.patch.object(mod, "list_open_secret_alerts", return_value=[]):
            self.assertEqual(mod.main(), 0)

    def test_code_alerts_ignore_unanalyzed_branch_ref(self):
        mod = load_module("github_alert_gate", "scripts/checks/github_alert_gate.py")

        with unittest.mock.patch.object(
            mod,
            "gh_api_json",
            side_effect=RuntimeError("gh: No commit found for the ref (HTTP 404)"),
        ):
            alerts = mod.list_open_code_alerts(
                "xiaojiou176-open/apple-notes-snapshot",
                "refs/heads/codex/test-branch",
            )
        self.assertEqual(alerts, [])

    def test_code_alerts_ignore_fixed_instances(self):
        mod = load_module("github_alert_gate", "scripts/checks/github_alert_gate.py")

        payload = [
            {"state": None, "most_recent_instance": {"state": "fixed"}},
            {"state": "open", "most_recent_instance": {"state": "open"}},
        ]
        with unittest.mock.patch.object(mod, "gh_api_json", return_value=payload):
            alerts = mod.list_open_code_alerts(
                "xiaojiou176-open/apple-notes-snapshot",
                "refs/pull/7/merge",
            )
        self.assertEqual(len(alerts), 1)

    def test_code_alerts_skip_in_actions_pull_request_when_integration_token_lacks_access(self):
        mod = load_module("github_alert_gate", "scripts/checks/github_alert_gate.py")

        env = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_EVENT_NAME": "pull_request",
        }
        with unittest.mock.patch.dict(mod.os.environ, env, clear=True):
            with unittest.mock.patch.object(
                mod,
                "gh_api_json",
                side_effect=RuntimeError("gh: Resource not accessible by integration (HTTP 403)"),
            ):
                alerts = mod.list_open_code_alerts(
                    "xiaojiou176-open/apple-notes-snapshot",
                    "refs/pull/9/merge",
                )
        self.assertEqual(alerts, [])

    def test_secret_alerts_skip_in_actions_when_integration_token_lacks_access(self):
        mod = load_module("github_alert_gate", "scripts/checks/github_alert_gate.py")

        with unittest.mock.patch.dict(mod.os.environ, {"GITHUB_ACTIONS": "true"}, clear=True):
            with unittest.mock.patch.object(
                mod,
                "gh_api_json",
                side_effect=RuntimeError("gh: Resource not accessible by integration (HTTP 403)"),
            ):
                alerts = mod.list_open_secret_alerts("xiaojiou176-open/apple-notes-snapshot")
        self.assertEqual(alerts, [])


if __name__ == "__main__":
    unittest.main()
