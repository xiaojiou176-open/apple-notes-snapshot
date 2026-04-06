import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import textwrap
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class WebServerE2ETests(unittest.TestCase):
    def start_server(self, env, port):
        repo_root = Path(__file__).resolve().parents[2]
        server_script = repo_root / "scripts" / "ops" / "web_server.py"
        return subprocess.Popen(
            [sys.executable, str(server_script), "--host", "127.0.0.1", "--port", str(port)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def wait_for_server(self, port, headers=None, expected_statuses=None):
        expected = expected_statuses or {200}
        deadline = time.time() + 5
        last_error = None
        while time.time() < deadline:
            try:
                req = Request(f"http://127.0.0.1:{port}/api/health", headers=headers or {})
                with urlopen(req, timeout=1) as resp:
                    if resp.status in expected:
                        return
            except HTTPError as exc:
                if exc.code in expected:
                    return
                last_error = exc
            except Exception as exc:
                last_error = exc
                time.sleep(0.1)
        raise AssertionError(f"server not responding: {last_error}")

    def request_json(self, url, headers=None, payload=None, method=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = Request(url, data=data, headers=headers or {}, method=method)
        try:
            with urlopen(req, timeout=2) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8")
            try:
                payload = json.loads(body)
            except Exception:
                payload = {"raw": body}
            return exc.code, payload

    def test_end_to_end_actions_and_auth(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            record = tmp_path / "notesctl_calls.txt"
            stub = tmp_path / "notesctl_stub.py"
            stub.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import json
                    import os
                    import sys

                    record = os.environ.get("NOTESCTL_RECORD")
                    if record:
                        with open(record, "a", encoding="utf-8") as handle:
                            handle.write(" ".join(sys.argv[1:]) + "\\n")

                    trigger_record = os.environ.get("NOTESCTL_TRIGGER_RECORD")
                    if trigger_record:
                        with open(trigger_record, "a", encoding="utf-8") as handle:
                            handle.write(os.environ.get("NOTES_SNAPSHOT_TRIGGER_SOURCE", "") + "\\n")

                    env_record = os.environ.get("NOTESCTL_ENV_RECORD")
                    if env_record and os.environ.get("NOTES_SNAPSHOT_VENDOR_REF"):
                        with open(env_record, "a", encoding="utf-8") as handle:
                            handle.write(os.environ.get("NOTES_SNAPSHOT_VENDOR_REF", "") + "\\n")

                    args = sys.argv[1:]
                    if args == ["doctor", "--json"]:
                        print(json.dumps({
                            "repo_root": "/tmp/repo",
                            "vendor_dir": "/tmp/repo/vendor/notes-exporter",
                            "state_dir": "/tmp/state",
                            "operator_summary": "The deterministic control-room surfaces are present; use warnings below to inspect any remaining gaps.",
                            "warnings": [],
                            "dependencies": {
                                "python_bin": "python3",
                                "osascript": True,
                                "launchctl": True,
                                "plutil": True,
                                "timeout_bin": ""
                            }
                        }))
                    elif args and args[0] == "aggregate":
                        print(json.dumps({
                            "summary": {
                                "recent_run_count": 1,
                                "success_count": 1,
                                "failed_count": 0,
                                "latest_status": "success",
                                "top_failure_reason": "",
                                "trigger_sources": {"manual": 1}
                            },
                            "runs": []
                        }))
                    elif "--json" in args:
                        print(json.dumps({"ok": True, "args": args}))
                    else:
                        print("ok")
                    """
                ),
                encoding="utf-8",
            )
            stub.chmod(0o755)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]

            log_dir = tmp_path / "logs"
            state_dir = log_dir / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            metrics = state_dir / "metrics.jsonl"
            metrics.write_text("{\"event\": \"run\"}\n", encoding="utf-8")
            (log_dir / "stdout.log").write_text("2024-01-01 00:00:00 ok\n", encoding="utf-8")

            env = os.environ.copy()
            env["NOTES_SNAPSHOT_WEB_TOKEN"] = "testtoken"
            env["NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN"] = "1"
            env["NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN_FOR_STATIC"] = "1"
            env["NOTES_SNAPSHOT_WEB_ALLOW_REMOTE"] = "0"
            env["NOTES_SNAPSHOT_WEB_ALLOW_IPS"] = "127.0.0.1/32"
            env["NOTES_SNAPSHOT_WEB_TOKEN_SCOPES"] = "all"
            env["NOTES_SNAPSHOT_WEB_HOST"] = "127.0.0.1"
            env["NOTES_SNAPSHOT_WEB_NOTESCTL"] = str(stub)
            env["NOTESCTL_RECORD"] = str(record)
            env["NOTESCTL_TRIGGER_RECORD"] = str(tmp_path / "trigger_calls.txt")
            env["NOTESCTL_ENV_RECORD"] = str(tmp_path / "env_calls.txt")
            env["NOTES_SNAPSHOT_LOG_DIR"] = str(log_dir)
            env["NOTES_SNAPSHOT_STATE_DIR"] = str(state_dir)
            env["NOTES_SNAPSHOT_WEB_RATE_LIMIT_MAX"] = "0"
            env["NOTES_SNAPSHOT_WEB_ACTION_COOLDOWNS"] = "off"

            proc = self.start_server(env, port)
            try:
                self.wait_for_server(port, {"Authorization": "Bearer testtoken"})

                # Unauthorized should fail
                status, payload = self.request_json(f"http://127.0.0.1:{port}/api/health")
                self.assertEqual(status, 401)
                self.assertEqual(payload.get("error"), "unauthorized")

                # Health with token
                status, payload = self.request_json(
                    f"http://127.0.0.1:{port}/api/health",
                    headers={"Authorization": "Bearer testtoken"},
                )
                self.assertEqual(status, 200)
                self.assertTrue(payload.get("ok"))

                # Status (JSON)
                status, payload = self.request_json(
                    f"http://127.0.0.1:{port}/api/status",
                    headers={"Authorization": "Bearer testtoken"},
                )
                self.assertEqual(status, 200)
                self.assertTrue(payload.get("ok"))
                self.assertIn("args", payload.get("data", {}))

                # Access (JSON)
                status, payload = self.request_json(
                    f"http://127.0.0.1:{port}/api/access",
                    headers={"Authorization": "Bearer testtoken"},
                )
                self.assertEqual(status, 200)
                self.assertTrue(payload.get("ok"))

                # Metrics from file
                status, payload = self.request_json(
                    f"http://127.0.0.1:{port}/api/metrics?tail=5",
                    headers={"Authorization": "Bearer testtoken"},
                )
                self.assertEqual(status, 200)
                self.assertTrue(payload.get("ok"))
                self.assertEqual(len(payload.get("entries", [])), 1)

                status, payload = self.request_json(
                    f"http://127.0.0.1:{port}/api/recent-runs?tail=5",
                    headers={"Authorization": "Bearer testtoken"},
                )
                self.assertEqual(status, 200)
                self.assertTrue(payload.get("ok"))
                self.assertIn("summary", payload.get("data", {}))

                # log-health and doctor (JSON)
                status, payload = self.request_json(
                    f"http://127.0.0.1:{port}/api/log-health?tail=3",
                    headers={"Authorization": "Bearer testtoken"},
                )
                self.assertEqual(status, 200)
                self.assertTrue(payload.get("ok"))

                status, payload = self.request_json(
                    f"http://127.0.0.1:{port}/api/doctor",
                    headers={"Authorization": "Bearer testtoken"},
                )
                self.assertEqual(status, 200)
                self.assertTrue(payload.get("ok"))
                self.assertIn("operator_summary", payload.get("data", {}))

                # Static index
                req = Request(f"http://127.0.0.1:{port}/")
                with self.assertRaises(HTTPError) as ctx:
                    urlopen(req, timeout=2)
                self.assertEqual(ctx.exception.code, 401)

                req = Request(f"http://127.0.0.1:{port}/", headers={"Authorization": "Bearer testtoken"})
                with urlopen(req, timeout=2) as resp:
                    html = resp.read().decode("utf-8")
                self.assertIn("Notes Snapshot Console", html)
                self.assertIn("Doctor summary not loaded yet.", html)
                self.assertIn("Recent Runs", html)
                self.assertIn('id="locale-switcher"', html)
                self.assertIn('data-i18n="locale.labelText"', html)
                self.assertIn('value="zh-CN"', html)
                self.assertIn('id="action-announcer"', html)
                self.assertIn('aria-live="polite"', html)
                self.assertIn('id="recent-runs-trend"', html)
                self.assertIn('id="recent-runs-streak"', html)
                self.assertIn('id="recent-runs-change-summary"', html)
                self.assertIn('id="recent-runs-failure-clusters"', html)

                req = Request(f"http://127.0.0.1:{port}/app.js", headers={"Authorization": "Bearer testtoken"})
                with urlopen(req, timeout=2) as resp:
                    app_js = resp.read().decode("utf-8")
                self.assertIn("window.NotesSnapshotI18n", app_js)
                self.assertNotIn("Web：", app_js)
                self.assertNotIn("unknown error", app_js)
                self.assertNotIn("file: ${result.file}", app_js)
                self.assertIn("formatTimestamp", app_js)
                self.assertIn("computeBannerMessage", app_js)

                req = Request(f"http://127.0.0.1:{port}/i18n.js", headers={"Authorization": "Bearer testtoken"})
                with urlopen(req, timeout=2) as resp:
                    i18n_js = resp.read().decode("utf-8")
                self.assertIn("notes_snapshot_web_locale", i18n_js)
                self.assertIn("NotesSnapshotI18n", i18n_js)
                self.assertIn("Simplified Chinese", i18n_js)
                self.assertIn("webActionSource", i18n_js)
                self.assertIn("actionFileLabel", i18n_js)
                self.assertIn("unknownError", i18n_js)
                self.assertIn("recentTrend", i18n_js)
                self.assertIn("changeSummary", i18n_js)
                self.assertIn("workflowHint", i18n_js)

                # Install action
                status, body = self.request_json(
                    f"http://127.0.0.1:{port}/api/install",
                    headers={
                        "Authorization": "Bearer testtoken",
                        "Content-Type": "application/json",
                    },
                    payload={"minutes": 15, "load": True, "web": False},
                    method="POST",
                )
                self.assertEqual(status, 200)
                self.assertTrue(body.get("ok"))

                # Ensure action
                status, body = self.request_json(
                    f"http://127.0.0.1:{port}/api/ensure",
                    headers={
                        "Authorization": "Bearer testtoken",
                        "Content-Type": "application/json",
                    },
                    payload={},
                    method="POST",
                )
                self.assertEqual(status, 200)
                self.assertTrue(body.get("ok"))

                # Invalid update-vendor ref
                status, body = self.request_json(
                    f"http://127.0.0.1:{port}/api/update-vendor",
                    headers={
                        "Authorization": "Bearer testtoken",
                        "Content-Type": "application/json",
                    },
                    payload={"ref": "bad ref"},
                    method="POST",
                )
                self.assertEqual(status, 400)
                self.assertEqual(body.get("error"), "invalid_ref")

                # Invalid rotate-logs scope
                status, body = self.request_json(
                    f"http://127.0.0.1:{port}/api/rotate-logs",
                    headers={
                        "Authorization": "Bearer testtoken",
                        "Content-Type": "application/json",
                    },
                    payload={"scope": "bad"},
                    method="POST",
                )
                self.assertEqual(status, 400)
                self.assertEqual(body.get("error"), "invalid_scope")

                # Invalid log type
                status, body = self.request_json(
                    f"http://127.0.0.1:{port}/api/logs",
                    headers={
                        "Authorization": "Bearer testtoken",
                        "Content-Type": "application/json",
                    },
                    payload={"type": "nope", "tail": 5},
                    method="POST",
                )
                self.assertEqual(status, 400)
                self.assertEqual(body.get("error"), "invalid_log_type")

                # Valid log type via logs endpoint
                status, body = self.request_json(
                    f"http://127.0.0.1:{port}/api/logs",
                    headers={
                        "Authorization": "Bearer testtoken",
                        "Content-Type": "application/json",
                    },
                    payload={"type": "stdout", "tail": 1},
                    method="POST",
                )
                self.assertEqual(status, 200)
                self.assertTrue(body.get("ok"))
                self.assertEqual(body.get("lines"), ["2024-01-01 00:00:00 ok"])

                # rotate-logs valid scope
                status, body = self.request_json(
                    f"http://127.0.0.1:{port}/api/rotate-logs",
                    headers={
                        "Authorization": "Bearer testtoken",
                        "Content-Type": "application/json",
                    },
                    payload={"scope": "stdout"},
                    method="POST",
                )
                self.assertEqual(status, 200)
                self.assertTrue(body.get("ok"))

                # update-vendor valid ref
                status, body = self.request_json(
                    f"http://127.0.0.1:{port}/api/update-vendor",
                    headers={
                        "Authorization": "Bearer testtoken",
                        "Content-Type": "application/json",
                    },
                    payload={"ref": "v1.2.3", "commit": True, "dry_run": True},
                    method="POST",
                )
                self.assertEqual(status, 200)
                self.assertTrue(body.get("ok"))

                # permissions action
                status, body = self.request_json(
                    f"http://127.0.0.1:{port}/api/permissions",
                    headers={
                        "Authorization": "Bearer testtoken",
                        "Content-Type": "application/json",
                    },
                    payload={},
                    method="POST",
                )
                self.assertEqual(status, 200)
                self.assertTrue(body.get("ok"))

                # run + verify + fix + self-heal actions
                for action in ("run", "verify", "fix", "self-heal"):
                    status, body = self.request_json(
                        f"http://127.0.0.1:{port}/api/{action}",
                        headers={
                            "Authorization": "Bearer testtoken",
                            "Content-Type": "application/json",
                        },
                        payload={},
                        method="POST",
                    )
                    self.assertEqual(status, 200)
                    self.assertTrue(body.get("ok"))

                # Verify notesctl args were captured
                calls = record.read_text(encoding="utf-8").splitlines()
                env_calls = (tmp_path / "env_calls.txt").read_text(encoding="utf-8").splitlines()
                self.assertTrue(any("install --minutes 15 --load --no-web" in line for line in calls))
                self.assertTrue(any("ensure --json" in line for line in calls))
                self.assertTrue(any("status --json" in line for line in calls))
                self.assertTrue(any("rotate-logs --stdout" in line for line in calls))
                self.assertTrue(any("update-vendor-commit --patch-dry-run" in line for line in calls))
                self.assertIn("v1.2.3", env_calls)
                self.assertTrue(any("doctor --json" in line for line in calls))
                self.assertTrue(any("log-health --json --tail 3" in line for line in calls))
                self.assertTrue(any("run --no-status" in line for line in calls))
                self.assertTrue(any("verify" in line for line in calls))
                self.assertTrue(any("fix" in line for line in calls))
                self.assertTrue(any("self-heal" in line for line in calls))

                triggers = (tmp_path / "trigger_calls.txt").read_text(encoding="utf-8").splitlines()
                triggers = [line for line in triggers if line.strip()]
                self.assertIn("web:install", triggers)
                self.assertIn("web:ensure", triggers)
                self.assertIn("web:run", triggers)
                self.assertIn("web:verify", triggers)
                self.assertIn("web:fix", triggers)
                self.assertIn("web:self-heal", triggers)
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()

    def test_scope_enforcement(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            stub = tmp_path / "notesctl_stub.py"
            stub.write_text("print('ok')\n", encoding="utf-8")
            stub.chmod(0o755)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]

            env = os.environ.copy()
            env["NOTES_SNAPSHOT_WEB_TOKEN"] = "scopetoken"
            env["NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN"] = "1"
            env["NOTES_SNAPSHOT_WEB_ALLOW_REMOTE"] = "0"
            env["NOTES_SNAPSHOT_WEB_ALLOW_IPS"] = "127.0.0.1/32"
            env["NOTES_SNAPSHOT_WEB_TOKEN_SCOPES"] = "read"
            env["NOTES_SNAPSHOT_WEB_HOST"] = "127.0.0.1"
            env["NOTES_SNAPSHOT_WEB_NOTESCTL"] = str(stub)

            proc = self.start_server(env, port)
            try:
                self.wait_for_server(port, {"Authorization": "Bearer scopetoken"})
                status, payload = self.request_json(
                    f"http://127.0.0.1:{port}/api/run",
                    headers={"Authorization": "Bearer scopetoken"},
                    payload={},
                    method="POST",
                )
                self.assertEqual(status, 403)
                self.assertEqual(payload.get("error"), "insufficient_scope")
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()

    def test_allowlist_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            stub = tmp_path / "notesctl_stub.py"
            stub.write_text("print('ok')\n", encoding="utf-8")
            stub.chmod(0o755)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]

            env = os.environ.copy()
            env["NOTES_SNAPSHOT_WEB_TOKEN"] = "blocktoken"
            env["NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN"] = "1"
            env["NOTES_SNAPSHOT_WEB_ALLOW_REMOTE"] = "0"
            env["NOTES_SNAPSHOT_WEB_ALLOW_IPS"] = "10.0.0.1/32"
            env["NOTES_SNAPSHOT_WEB_TOKEN_SCOPES"] = "all"
            env["NOTES_SNAPSHOT_WEB_HOST"] = "127.0.0.1"
            env["NOTES_SNAPSHOT_WEB_NOTESCTL"] = str(stub)

            proc = self.start_server(env, port)
            try:
                self.wait_for_server(port, {"Authorization": "Bearer blocktoken"}, expected_statuses={403})
                status, payload = self.request_json(
                    f"http://127.0.0.1:{port}/api/health",
                    headers={"Authorization": "Bearer blocktoken"},
                )
                self.assertEqual(status, 403)
                self.assertEqual(payload.get("error"), "ip_not_allowed")
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()

    def test_readonly_blocks_actions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            stub = tmp_path / "notesctl_stub.py"
            stub.write_text("print('ok')\n", encoding="utf-8")
            stub.chmod(0o755)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]

            env = os.environ.copy()
            env["NOTES_SNAPSHOT_WEB_TOKEN"] = "readonlytoken"
            env["NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN"] = "1"
            env["NOTES_SNAPSHOT_WEB_READONLY"] = "1"
            env["NOTES_SNAPSHOT_WEB_ALLOW_REMOTE"] = "0"
            env["NOTES_SNAPSHOT_WEB_ALLOW_IPS"] = "127.0.0.1/32"
            env["NOTES_SNAPSHOT_WEB_TOKEN_SCOPES"] = "all"
            env["NOTES_SNAPSHOT_WEB_HOST"] = "127.0.0.1"
            env["NOTES_SNAPSHOT_WEB_NOTESCTL"] = str(stub)

            proc = self.start_server(env, port)
            try:
                self.wait_for_server(port, {"Authorization": "Bearer readonlytoken"})
                status, payload = self.request_json(
                    f"http://127.0.0.1:{port}/api/run",
                    headers={"Authorization": "Bearer readonlytoken"},
                    payload={},
                    method="POST",
                )
                self.assertEqual(status, 403)
                self.assertEqual(payload.get("error"), "readonly")
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()


if __name__ == "__main__":
    unittest.main()
