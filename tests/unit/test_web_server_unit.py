import io
import json
import os
import tempfile
import importlib.util
import unittest
import ipaddress
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


def load_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "ops" / "web_server.py"
    spec = importlib.util.spec_from_file_location("web_server", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DummyHandler:
    def __init__(self, headers):
        self.headers = headers


class DummyReadHandler:
    def __init__(self, data, headers=None):
        self.rfile = io.BytesIO(data)
        self.headers = headers or {}


class WebServerUnitTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        self.mod.WEB_REQUIRE_TOKEN = False
        self.mod.WEB_READONLY = False
        self.mod.WEB_TOKEN = ""
        self.mod.WEB_ALLOW_REMOTE = False
        self.mod.ALLOW_IPS = []
        self.mod.TOKEN_SCOPES = None
        self.mod.TOKEN_SCOPES_ERROR = None
        self.mod.ACTION_ALLOWLIST = None
        self.mod.ACTION_ALLOWLIST_ERROR = None
        self.mod.ACTION_COOLDOWNS = {}
        self.mod.ACTION_LAST_RUN = {}

    def build_handler(self):
        handler = object.__new__(self.mod.NotesHandler)
        handler.headers = {}
        handler.rfile = io.BytesIO(b"{}")
        handler.wfile = io.BytesIO()
        handler.client_address = ("127.0.0.1", 12345)
        handler._headers = []
        handler._status = None
        handler.send_response = lambda code: setattr(handler, "_status", code)
        handler.send_header = lambda k, v=None: handler._headers.append((k, v))
        handler.end_headers = lambda: None
        return handler

    def test_safe_int(self):
        self.assertEqual(self.mod.safe_int("10", 0), 10)
        self.assertEqual(self.mod.safe_int("-1", 0), -1)
        self.assertEqual(self.mod.safe_int("bad", 7), 7)

    def test_env_bool(self):
        key = "TEST_WEB_BOOL"
        old = os.environ.get(key)
        try:
            os.environ[key] = "1"
            self.assertTrue(self.mod.env_bool(key, False))
            os.environ[key] = "false"
            self.assertFalse(self.mod.env_bool(key, True))
            del os.environ[key]
            self.assertTrue(self.mod.env_bool(key, True))
        finally:
            if old is not None:
                os.environ[key] = old
            elif key in os.environ:
                del os.environ[key]

    def test_sanitize_ref(self):
        self.assertEqual(self.mod.sanitize_ref("v1.2.3"), "v1.2.3")
        self.assertIsNone(self.mod.sanitize_ref("bad;rm -rf"))
        self.assertIsNone(self.mod.sanitize_ref("space here"))
        self.assertEqual(self.mod.sanitize_ref(""), "")

    def test_sanitize_notesctl_args(self):
        self.assertEqual(
            self.mod.sanitize_notesctl_args(["run", "--no-status"]),
            ["run", "--no-status"],
        )
        self.assertIsNone(self.mod.sanitize_notesctl_args(["bad arg"]))
        self.assertIsNone(self.mod.sanitize_notesctl_args(["bad;rm"]))

    def test_build_notesctl_invocation(self):
        args, env = self.mod.build_notesctl_invocation("run_no_status")
        self.assertEqual(args, ["run", "--no-status"])
        self.assertEqual(env, {})

        fixed_commands = {
            "setup": ["setup"],
            "verify": ["verify"],
            "fix": ["fix"],
            "self_heal": ["self-heal"],
            "permissions": ["permissions"],
            "status_json": ["status", "--json"],
            "doctor_json": ["doctor", "--json"],
            "ensure_json": ["ensure", "--json"],
        }
        for command_name, expected in fixed_commands.items():
            args, env = self.mod.build_notesctl_invocation(command_name)
            self.assertEqual(args, expected)
            self.assertEqual(env, {})

        args, env = self.mod.build_notesctl_invocation(
            "update_vendor_commit",
            options={"ref": "v1.2.3", "dry_run": True},
        )
        self.assertEqual(args, ["update-vendor-commit", "--patch-dry-run"])
        self.assertEqual(env, {"NOTES_SNAPSHOT_VENDOR_REF": "v1.2.3"})

        args, env = self.mod.build_notesctl_invocation(
            "install",
            options={"minutes": 15, "load": True},
        )
        self.assertEqual(args, ["install", "--minutes", "15", "--load", "--web"])
        self.assertEqual(env, {})

    def test_normalize_host(self):
        self.mod.WEB_ALLOW_REMOTE = False
        self.mod.WEB_TOKEN = ""
        self.mod.WEB_REQUIRE_TOKEN = True
        host, err = self.mod.normalize_host("0.0.0.0")
        self.assertEqual(host, "127.0.0.1")
        self.assertEqual(err, "remote_blocked")

        self.mod.WEB_ALLOW_REMOTE = True
        self.mod.WEB_TOKEN = ""
        self.mod.WEB_REQUIRE_TOKEN = True
        host, err = self.mod.normalize_host("0.0.0.0")
        self.assertIsNone(host)
        self.assertEqual(err, "token_required")

        self.mod.WEB_ALLOW_REMOTE = True
        self.mod.WEB_TOKEN = "token"
        self.mod.WEB_REQUIRE_TOKEN = True
        host, err = self.mod.normalize_host("0.0.0.0")
        self.assertEqual(host, "0.0.0.0")
        self.assertIsNone(err)

        self.mod.WEB_ALLOW_REMOTE = True
        self.mod.WEB_TOKEN = ""
        self.mod.WEB_REQUIRE_TOKEN = False
        host, err = self.mod.normalize_host("0.0.0.0")
        self.assertEqual(host, "0.0.0.0")
        self.assertIsNone(err)

        host, err = self.mod.normalize_host("localhost")
        self.assertEqual(host, "127.0.0.1")
        self.assertIsNone(err)

        host, err = self.mod.normalize_host("")
        self.assertEqual(host, "127.0.0.1")
        self.assertIsNone(err)

    def test_extract_token(self):
        parsed = urlparse("/api/status?token=query")

        handler = DummyHandler({"Authorization": "Bearer header"})
        token = self.mod.extract_token_from_request(handler, parsed)
        self.assertEqual(token, "header")

        handler = DummyHandler({"X-Notes-Token": "custom"})
        token = self.mod.extract_token_from_request(handler, parsed)
        self.assertEqual(token, "custom")

        handler = DummyHandler({})
        token = self.mod.extract_token_from_request(handler, parsed)
        self.assertEqual(token, "query")

    def test_parse_bool(self):
        self.assertTrue(self.mod.parse_bool(True))
        self.assertTrue(self.mod.parse_bool("yes"))
        self.assertFalse(self.mod.parse_bool("no"))
        self.assertFalse(self.mod.parse_bool(0))
        self.assertFalse(self.mod.parse_bool(None))

    def test_clamp_int(self):
        self.assertEqual(self.mod.clamp_int("10", 5, 1, 9), 9)
        self.assertEqual(self.mod.clamp_int("-1", 5, 1, 9), 1)
        self.assertEqual(self.mod.clamp_int("7", 5, 1, 9), 7)
        self.assertEqual(self.mod.clamp_int("bad", 5, 1, 9), 5)

    def test_parse_scopes(self):
        scopes, err = self.mod.parse_scopes("")
        self.assertIsNone(scopes)
        self.assertIsNone(err)
        scopes, err = self.mod.parse_scopes("all")
        self.assertIsNone(scopes)
        self.assertIsNone(err)
        scopes, err = self.mod.parse_scopes("badscope")
        self.assertIsNone(scopes)
        self.assertTrue(err.startswith("invalid_scopes:"))
        scopes, err = self.mod.parse_scopes("Read,Run")
        self.assertEqual(scopes, {"read", "run"})
        self.assertIsNone(err)

    def test_parse_allow_ips(self):
        allow, err = self.mod.parse_allow_ips("127.0.0.1/32,::1,localhost")
        self.assertIsNone(err)
        self.assertTrue(allow)
        allow_ip, err_ip = self.mod.parse_allow_ips("10.0.0.1")
        self.assertIsNone(err_ip)
        self.assertEqual(len(allow_ip), 1)
        bad_allow, bad_err = self.mod.parse_allow_ips("bad-ip")
        self.assertIsNone(bad_allow)
        self.assertTrue(bad_err.startswith("invalid_allow_ip:"))

    def test_normalize_client_ip(self):
        mapped = self.mod.normalize_client_ip("::ffff:127.0.0.1")
        self.assertEqual(str(mapped), "127.0.0.1")
        self.assertIsNone(self.mod.normalize_client_ip("not-an-ip"))

    def test_parse_action_allowlist(self):
        actions, err = self.mod.parse_action_allowlist("")
        self.assertIsNone(actions)
        self.assertIsNone(err)
        actions, err = self.mod.parse_action_allowlist("all")
        self.assertIsNone(actions)
        self.assertIsNone(err)
        actions, err = self.mod.parse_action_allowlist("run,verify")
        self.assertEqual(actions, {"run", "verify"})
        self.assertIsNone(err)
        actions, err = self.mod.parse_action_allowlist("bad-action")
        self.assertIsNone(actions)
        self.assertTrue(err.startswith("invalid_actions:"))

    def test_parse_action_cooldowns(self):
        cooldowns, err = self.mod.parse_action_cooldowns("", {"run": 60})
        self.assertIsNone(err)
        self.assertEqual(cooldowns.get("run"), 60)
        cooldowns, err = self.mod.parse_action_cooldowns("off", {"run": 60})
        self.assertIsNone(err)
        self.assertEqual(cooldowns, {})
        cooldowns, err = self.mod.parse_action_cooldowns("run=30,install=60", {})
        self.assertIsNone(err)
        self.assertEqual(cooldowns.get("run"), 30)
        self.assertIsNone(self.mod.parse_action_cooldowns("bad", {})[0])
        self.assertTrue(self.mod.parse_action_cooldowns("bad", {})[1].startswith("invalid_cooldown:"))

    def test_validate_action_scopes(self):
        err = self.mod.validate_action_scopes({"run", "install"}, {"read"})
        self.assertTrue(err.startswith("action_scope_mismatch:"))
        self.assertIsNone(self.mod.validate_action_scopes({"run"}, {"run", "read"}))
        self.assertIsNone(self.mod.validate_action_scopes(None, {"run"}))
        self.assertIsNone(self.mod.validate_action_scopes({"run"}, None))

    def test_compute_allowed_actions(self):
        self.mod.WEB_READONLY = False
        self.mod.ACTION_ALLOWLIST = {"run", "install"}
        self.mod.TOKEN_SCOPES = {"run"}
        allowed = self.mod.compute_allowed_actions()
        self.assertEqual(allowed, ["run"])
        self.mod.WEB_READONLY = True
        self.assertEqual(self.mod.compute_allowed_actions(), [])

    def test_rate_limit(self):
        old_window = self.mod.WEB_RATE_LIMIT_WINDOW_SEC
        old_max = self.mod.WEB_RATE_LIMIT_MAX
        old_buckets = self.mod.RATE_LIMIT_BUCKETS
        try:
            self.mod.WEB_RATE_LIMIT_WINDOW_SEC = 60
            self.mod.WEB_RATE_LIMIT_MAX = 1
            self.mod.RATE_LIMIT_BUCKETS = {}
            self.assertIsNone(self.mod.check_rate_limit("127.0.0.1"))
            retry = self.mod.check_rate_limit("127.0.0.1")
            self.assertIsInstance(retry, int)
            self.assertGreaterEqual(retry, 1)
        finally:
            self.mod.WEB_RATE_LIMIT_WINDOW_SEC = old_window
            self.mod.WEB_RATE_LIMIT_MAX = old_max
            self.mod.RATE_LIMIT_BUCKETS = old_buckets

    def test_action_cooldown(self):
        old_cooldowns = self.mod.ACTION_COOLDOWNS
        old_last = self.mod.ACTION_LAST_RUN
        try:
            self.mod.ACTION_COOLDOWNS = {"run": 60}
            self.mod.ACTION_LAST_RUN = {}
            self.assertIsNone(self.mod.check_action_cooldown("run"))
            retry = self.mod.check_action_cooldown("run")
            self.assertIsInstance(retry, int)
            self.assertGreaterEqual(retry, 1)
        finally:
            self.mod.ACTION_COOLDOWNS = old_cooldowns
            self.mod.ACTION_LAST_RUN = old_last

    def test_read_json_body(self):
        payload = {"a": 1}
        raw = json.dumps(payload).encode("utf-8")
        handler = DummyReadHandler(raw, headers={"Content-Length": str(len(raw))})
        data = self.mod.read_json_body(handler)
        self.assertEqual(data, payload)
        empty = DummyReadHandler(b"", headers={"Content-Length": "0"})
        self.assertEqual(self.mod.read_json_body(empty), {})
        with self.assertRaises(ValueError):
            big = DummyReadHandler(b"x" * (self.mod.MAX_BODY_BYTES + 1), headers={"Content-Length": str(self.mod.MAX_BODY_BYTES + 1)})
            self.mod.read_json_body(big)
        with self.assertRaises(ValueError):
            bad = DummyReadHandler(b"{bad", headers={"Content-Length": "4"})
            self.mod.read_json_body(bad)

    def test_file_helpers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "log.txt"
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            path.write_text(
                f"{now} recent\n"
                "2024-01-01 00:00:01 alpha\n"
                "2024-01-01 00:00:02 beta\n"
                "2024-99-99 99:99:99 badts\n"
                "line without ts\n",
                encoding="utf-8",
            )
            tail = self.mod.tail_file(str(path), 2)
            self.assertTrue(tail.get("ok"))
            self.assertEqual(len(tail.get("lines", [])), 2)

            filtered = self.mod.filter_since(str(path), 60)
            self.assertTrue(filtered.get("ok"))
            self.assertTrue(any("recent" in line for line in filtered.get("lines", [])))
            missing_filtered = self.mod.filter_since(str(Path(tmpdir) / "missing.log"), 1)
            self.assertFalse(missing_filtered.get("ok"))

            metrics = Path(tmpdir) / "metrics.jsonl"
            metrics.write_text("{\"event\": \"run\"}\n\ninvalid\n", encoding="utf-8")
            result = self.mod.load_metrics_jsonl(str(metrics), 5)
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("errors"), 1)
            result_empty = self.mod.load_metrics_jsonl(str(metrics), 1)
            self.assertTrue(result_empty.get("ok"))
            missing = self.mod.load_metrics_jsonl(str(Path(tmpdir) / "missing.jsonl"), 1)
            self.assertFalse(missing.get("ok"))
            missing_tail = self.mod.tail_file(str(Path(tmpdir) / "missing.log"), 1)
            self.assertFalse(missing_tail.get("ok"))

    def test_run_notesctl_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            script = Path(tmpdir) / "notesctl"
            script.write_text(
                "#!/bin/zsh\nprint \"{\\\"ok\\\": true, \\\"extra\\\": \\\"${EXTRA_ENV:-}\\\", \\\"vendor_ref\\\": \\\"${NOTES_SNAPSHOT_VENDOR_REF:-}\\\"}\"\n",
                encoding="utf-8",
            )
            script.chmod(0o755)
            self.mod.NOTESCTL_CANDIDATES = [script]
            result = self.mod.run_notesctl_json("status_json", 2, extra_env={"EXTRA_ENV": "yes"})
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("data", {}).get("extra"), "yes")
            vendor_result = self.mod.run_notesctl_json(
                "update_vendor_commit",
                2,
                options={"ref": "v1.2.3", "dry_run": True},
            )
            self.assertTrue(vendor_result.get("ok"))
            self.assertEqual(vendor_result.get("data", {}).get("vendor_ref"), "v1.2.3")
            bad_script = Path(tmpdir) / "bad"
            bad_script.write_text("#!/bin/zsh\necho 'not json'\n", encoding="utf-8")
            bad_script.chmod(0o755)
            self.mod.NOTESCTL_CANDIDATES = [bad_script]
            bad_result = self.mod.run_notesctl_json("status_json", 2)
            self.assertFalse(bad_result.get("ok"))
            self.mod.NOTESCTL_CANDIDATES = []
            missing_result = self.mod.run_notesctl_json("status_json", 1)
            self.assertFalse(missing_result.get("ok"))

    def test_run_notesctl_json_with_real_repo_doctor_command(self):
        repo_root = Path(__file__).resolve().parents[2]
        old_candidates = self.mod.NOTESCTL_CANDIDATES
        try:
            self.mod.NOTESCTL_CANDIDATES = [repo_root / "notesctl"]
            result = self.mod.run_notesctl_json("doctor_json", 10)
            self.assertTrue(result.get("ok"), result)
            data = result.get("data", {})
            self.assertIn("repo_root", data)
            self.assertIn("launchd_loaded", data)
            self.assertIn("warnings", data)
        finally:
            self.mod.NOTESCTL_CANDIDATES = old_candidates

    def test_run_notesctl_variants(self):
        # missing notesctl
        self.mod.NOTESCTL_CANDIDATES = []
        result = self.mod.run_notesctl_command("status_json", 1)
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("error"), "notesctl_not_found")

        # non-executable script uses /bin/zsh
        with tempfile.TemporaryDirectory() as tmpdir:
            script = Path(tmpdir) / "notesctl"
            script.write_text("echo ok\n", encoding="utf-8")
            self.mod.NOTESCTL_CANDIDATES = [script]
            result = self.mod.run_notesctl_command("status_json", 1)
            self.assertTrue(result.get("ok"))
            invalid = self.mod.run_notesctl_command("unknown", 1)
            self.assertFalse(invalid.get("ok"))
            self.assertEqual(invalid.get("error"), "invalid_args")

        # subprocess failure path
        old_run = self.mod.subprocess.run
        try:
            def boom(*args, **kwargs):
                raise RuntimeError("fail")
            self.mod.subprocess.run = boom
            self.mod.NOTESCTL_CANDIDATES = [Path(__file__)]
            result = self.mod.run_notesctl_command("status_json", 1)
            self.assertFalse(result.get("ok"))
            self.assertEqual(result.get("error"), "subprocess_failed")
        finally:
            self.mod.subprocess.run = old_run

    def test_resolve_notesctl_prefers_repo_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            candidate = Path(tmpdir) / "notesctl"
            candidate.write_text("#!/bin/zsh\necho ok\n", encoding="utf-8")
            candidate.chmod(0o755)
            old_candidates = self.mod.NOTESCTL_CANDIDATES
            try:
                self.mod.NOTESCTL_CANDIDATES = [candidate]
                resolved = self.mod.resolve_notesctl()
                self.assertEqual(Path(resolved), candidate)
            finally:
                self.mod.NOTESCTL_CANDIDATES = old_candidates

    def test_load_module_prefers_notesctl_override_env(self):
        key = "NOTES_SNAPSHOT_WEB_NOTESCTL"
        old = os.environ.get(key)
        with tempfile.TemporaryDirectory() as tmpdir:
            candidate = Path(tmpdir) / "notesctl"
            candidate.write_text("#!/bin/zsh\necho ok\n", encoding="utf-8")
            candidate.chmod(0o755)
            try:
                os.environ[key] = str(candidate)
                mod = load_module()
                self.assertTrue(mod.NOTESCTL_CANDIDATES)
                self.assertEqual(Path(mod.NOTESCTL_CANDIDATES[0]), candidate)
            finally:
                if old is not None:
                    os.environ[key] = old
                elif key in os.environ:
                    del os.environ[key]

    def test_safe_join(self):
        handler = self.build_handler()
        base = Path(tempfile.gettempdir())
        ok = handler.safe_join(base, "/index.html")
        self.assertIsNotNone(ok)
        bad = handler.safe_join(base, "/../etc/passwd")
        self.assertIsNone(bad)
        bad_type = handler.safe_join(base, None)
        self.assertIsNone(bad_type)
        bad_crlf = handler.safe_join(base, "/index.html\r\nX-Test: injected")
        self.assertIsNone(bad_crlf)

    def test_handle_api_and_action(self):
        self.mod.WEB_TOKEN = ""
        self.mod.WEB_ALLOW_REMOTE = False

        handler = self.build_handler()

        def fake_json(args, extra_env=None, options=None):
            return {"ok": True, "data": {"stub": True}}

        def fake_raw(args, timeout=None, extra_env=None, options=None):
            return {"ok": True, "stdout": "ok"}

        handler.respond_notesctl_json = fake_json
        handler.respond_notesctl_raw = fake_raw

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            state_dir = log_dir / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "metrics.jsonl").write_text("{\"event\": \"run\"}\n", encoding="utf-8")

            old_log = os.environ.get("NOTES_SNAPSHOT_LOG_DIR")
            old_state = os.environ.get("NOTES_SNAPSHOT_STATE_DIR")
            action_envs = []
            try:
                os.environ["NOTES_SNAPSHOT_LOG_DIR"] = str(log_dir)
                os.environ["NOTES_SNAPSHOT_STATE_DIR"] = str(state_dir)

                handler.handle_api(urlparse("/api/health"))
                handler.handle_api(urlparse("/api/status"))
                handler.handle_api(urlparse("/api/log-health?tail=5"))
                handler.handle_api(urlparse("/api/metrics?tail=1"))
                handler.handle_api(urlparse("/api/recent-runs?tail=5"))

                def track_json(args, extra_env=None):
                    action_envs.append(extra_env or {})
                    return fake_json(args, extra_env=extra_env)

                handler.respond_notesctl_json = track_json
                handler.handle_action(urlparse("/api/ensure"))
                self.assertTrue(action_envs)
                self.assertIn("NOTES_SNAPSHOT_TRIGGER_SOURCE", action_envs[-1])
            finally:
                if old_log is not None:
                    os.environ["NOTES_SNAPSHOT_LOG_DIR"] = old_log
                elif "NOTES_SNAPSHOT_LOG_DIR" in os.environ:
                    del os.environ["NOTES_SNAPSHOT_LOG_DIR"]
                if old_state is not None:
                    os.environ["NOTES_SNAPSHOT_STATE_DIR"] = old_state
                elif "NOTES_SNAPSHOT_STATE_DIR" in os.environ:
                    del os.environ["NOTES_SNAPSHOT_STATE_DIR"]

    def test_require_access_rejects_without_token(self):
        self.mod.WEB_REQUIRE_TOKEN = True
        self.mod.WEB_TOKEN = "secret"
        handler = self.build_handler()

        ok = handler.require_access(urlparse("/api/health"), "read")
        self.assertFalse(ok)
        self.assertEqual(handler._status, 401)

    def test_require_access_enforces_scope(self):
        self.mod.WEB_REQUIRE_TOKEN = True
        self.mod.WEB_TOKEN = "secret"
        self.mod.TOKEN_SCOPES = {"read"}
        handler = self.build_handler()
        handler.headers = {"Authorization": "Bearer secret"}

        ok = handler.require_access(urlparse("/api/run"), "run")
        self.assertFalse(ok)
        self.assertEqual(handler._status, 403)
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(body.get("error"), "insufficient_scope")

    def test_require_access_enforces_allowlist(self):
        self.mod.ALLOW_IPS = [ipaddress.ip_network("127.0.0.1/32")]
        handler = self.build_handler()
        handler.client_address = ("10.0.0.1", 12345)
        ok = handler.require_access(urlparse("/api/health"), "read")
        self.assertFalse(ok)
        self.assertEqual(handler._status, 403)
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(body.get("error"), "ip_not_allowed")

    def test_is_ip_allowed_match(self):
        self.mod.ALLOW_IPS = [ipaddress.ip_network("127.0.0.1/32")]
        handler = self.build_handler()
        handler.headers = {"Authorization": "Bearer ok"}
        self.mod.WEB_REQUIRE_TOKEN = True
        self.mod.WEB_TOKEN = "ok"
        ok = handler.require_access(urlparse("/api/health"), "read")
        self.assertTrue(ok)

    def test_ip_parse_failure_blocks(self):
        self.mod.ALLOW_IPS = [ipaddress.ip_network("127.0.0.1/32")]
        handler = self.build_handler()
        handler.client_address = ("not-an-ip", 12345)
        ok = handler.require_access(urlparse("/api/health"), "read")
        self.assertFalse(ok)
        self.assertEqual(handler._status, 403)

    def test_handle_action_requires_auth(self):
        self.mod.WEB_REQUIRE_TOKEN = True
        self.mod.WEB_TOKEN = "secret"
        handler = self.build_handler()
        handler.rfile = io.BytesIO(b"{}")
        handler.headers = {"Content-Length": "2"}
        handler.handle_action(urlparse("/api/run"))
        self.assertEqual(handler._status, 401)

    def test_handle_action_readonly(self):
        self.mod.WEB_READONLY = True
        handler = self.build_handler()
        handler.rfile = io.BytesIO(b"{}")
        handler.headers = {"Content-Length": "2"}
        handler.handle_action(urlparse("/api/run"))
        self.assertEqual(handler._status, 403)
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(body.get("error"), "readonly")

    def test_handle_action_allowlist(self):
        self.mod.ACTION_ALLOWLIST = {"run"}
        handler = self.build_handler()
        handler.rfile = io.BytesIO(b"{}")
        handler.headers = {"Content-Length": "2"}
        handler.handle_action(urlparse("/api/verify"))
        self.assertEqual(handler._status, 403)
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(body.get("error"), "action_not_allowed")

    def test_handle_action_content_type(self):
        handler = self.build_handler()
        handler.rfile = io.BytesIO(b"{}")
        handler.headers = {"Content-Length": "2", "Content-Type": "text/plain"}
        handler.handle_action(urlparse("/api/run"))
        self.assertEqual(handler._status, 415)
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(body.get("error"), "unsupported_media_type")

    def test_handle_api_requires_auth(self):
        self.mod.WEB_REQUIRE_TOKEN = True
        self.mod.WEB_TOKEN = "secret"
        handler = self.build_handler()
        handler.handle_api(urlparse("/api/status"))
        self.assertEqual(handler._status, 401)

    def test_do_get_post_ip_blocked(self):
        self.mod.ALLOW_IPS = [ipaddress.ip_network("10.0.0.1/32")]
        handler = self.build_handler()
        handler.client_address = ("127.0.0.1", 12345)
        handler.path = "/api/health"
        handler.do_GET()
        self.assertEqual(handler._status, 403)
        handler.path = "/api/run"
        handler.do_POST()
        self.assertEqual(handler._status, 403)

    def test_log_message_noop(self):
        handler = self.build_handler()
        handler.log_message("noop")

    def test_handler_errors_and_static(self):
        handler = self.build_handler()
        handler.rfile = io.BytesIO(b"{bad")
        handler.headers = {"Content-Length": "4"}
        handler.handle_action(urlparse("/api/ensure"))
        self.assertEqual(handler._status, 400)

        # simulate busy lock
        if self.mod.ACTION_LOCK.acquire(blocking=False):
            try:
                handler.rfile = io.BytesIO(b"{}")
                handler.headers = {"Content-Length": "2"}
                handler.handle_action(urlparse("/api/ensure"))
                self.assertEqual(handler._status, 409)
            finally:
                self.mod.ACTION_LOCK.release()

        # serve static with missing index
        with tempfile.TemporaryDirectory() as tmpdir:
            old_root = self.mod.WEB_ROOT
            try:
                self.mod.WEB_ROOT = Path(tmpdir)
                handler.serve_static(urlparse("/"))
                self.assertEqual(handler._status, 500)
            finally:
                self.mod.WEB_ROOT = old_root

        # serve static with existing file
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            (temp_root / "index.html").write_text("hello", encoding="utf-8")
            old_root = self.mod.WEB_ROOT
            try:
                self.mod.WEB_ROOT = temp_root
                handler.serve_static(urlparse("/"))
                self.assertEqual(handler._status, 200)
            finally:
                self.mod.WEB_ROOT = old_root

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            (temp_root / "index.html").write_text("hello", encoding="utf-8")
            old_root = self.mod.WEB_ROOT
            try:
                self.mod.WEB_ROOT = temp_root
                handler.serve_static(urlparse("/..\r\nX-Test: bad"))
                self.assertEqual(handler._status, 200)
            finally:
                self.mod.WEB_ROOT = old_root

        # serve static with unreadable file
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            target = temp_root / "secret.txt"
            target.write_text("secret", encoding="utf-8")
            os.chmod(target, 0o000)
            old_root = self.mod.WEB_ROOT
            try:
                self.mod.WEB_ROOT = temp_root
                handler.serve_static(urlparse("/secret.txt"))
                self.assertEqual(handler._status, 500)
            finally:
                os.chmod(target, 0o644)
                self.mod.WEB_ROOT = old_root

        # serve static with unknown content type
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            (temp_root / "file.unknownext").write_text("data", encoding="utf-8")
            old_root = self.mod.WEB_ROOT
            try:
                self.mod.WEB_ROOT = temp_root
                handler.serve_static(urlparse("/file.unknownext"))
                self.assertEqual(handler._status, 200)
                self.assertTrue(any("application/octet-stream" in (v or "") for _, v in handler._headers))
                self.assertTrue(any("Content-Security-Policy" == k for k, _ in handler._headers))
            finally:
                self.mod.WEB_ROOT = old_root

    def test_main_error_paths(self):
        old_root = self.mod.WEB_ROOT
        old_allow = self.mod.WEB_ALLOW_REMOTE
        old_token = self.mod.WEB_TOKEN
        old_require = self.mod.WEB_REQUIRE_TOKEN
        old_allow_ips_err = self.mod.ALLOW_IPS_ERROR
        old_scopes_err = self.mod.TOKEN_SCOPES_ERROR
        old_actions_err = self.mod.ACTION_ALLOWLIST_ERROR
        old_argv = os.sys.argv[:]
        try:
            self.mod.WEB_ROOT = Path("/no/such/web/root")
            os.sys.argv = ["web_server.py"]
            code = self.mod.main()
            self.assertEqual(code, 1)

            self.mod.WEB_ROOT = old_root
            self.mod.WEB_ALLOW_REMOTE = True
            self.mod.WEB_REQUIRE_TOKEN = True
            self.mod.WEB_TOKEN = ""
            os.sys.argv = ["web_server.py", "--host", "0.0.0.0", "--port", "0"]
            code = self.mod.main()
            self.assertEqual(code, 2)

            self.mod.WEB_ROOT = old_root
            self.mod.ALLOW_IPS_ERROR = "invalid_allow_ip:bad"
            os.sys.argv = ["web_server.py"]
            code = self.mod.main()
            self.assertEqual(code, 2)

            self.mod.WEB_ROOT = old_root
            self.mod.ALLOW_IPS_ERROR = None
            self.mod.TOKEN_SCOPES_ERROR = "invalid_scopes:bad"
            os.sys.argv = ["web_server.py"]
            code = self.mod.main()
            self.assertEqual(code, 2)

            self.mod.WEB_ROOT = old_root
            self.mod.TOKEN_SCOPES_ERROR = None
            self.mod.ACTION_ALLOWLIST_ERROR = "invalid_actions:bad"
            os.sys.argv = ["web_server.py"]
            code = self.mod.main()
            self.assertEqual(code, 2)
        finally:
            self.mod.WEB_ROOT = old_root
            self.mod.WEB_ALLOW_REMOTE = old_allow
            self.mod.WEB_TOKEN = old_token
            self.mod.WEB_REQUIRE_TOKEN = old_require
            self.mod.ALLOW_IPS_ERROR = old_allow_ips_err
            self.mod.TOKEN_SCOPES_ERROR = old_scopes_err
            self.mod.ACTION_ALLOWLIST_ERROR = old_actions_err
            os.sys.argv = old_argv

    def test_main_keyboard_interrupt(self):
        class DummyServer:
            def __init__(self, addr, handler):
                self.addr = addr
            def serve_forever(self):
                raise KeyboardInterrupt()

        old_server = self.mod.ThreadingHTTPServer
        old_root = self.mod.WEB_ROOT
        old_allow = self.mod.WEB_ALLOW_REMOTE
        old_require = self.mod.WEB_REQUIRE_TOKEN
        old_token = self.mod.WEB_TOKEN
        old_argv = os.sys.argv[:]
        try:
            self.mod.ThreadingHTTPServer = DummyServer
            self.mod.WEB_ROOT = Path(tempfile.gettempdir())
            self.mod.WEB_ALLOW_REMOTE = False
            self.mod.WEB_REQUIRE_TOKEN = False
            self.mod.WEB_TOKEN = ""
            os.sys.argv = ["web_server.py", "--host", "0.0.0.0", "--port", "0"]
            code = self.mod.main()
            self.assertEqual(code, 0)
        finally:
            self.mod.ThreadingHTTPServer = old_server
            self.mod.WEB_ROOT = old_root
            self.mod.WEB_ALLOW_REMOTE = old_allow
            self.mod.WEB_REQUIRE_TOKEN = old_require
            self.mod.WEB_TOKEN = old_token
            os.sys.argv = old_argv

    def test_main_token_required_branch(self):
        old_root = self.mod.WEB_ROOT
        old_require = self.mod.WEB_REQUIRE_TOKEN
        old_normalize = self.mod.normalize_host
        old_argv = os.sys.argv[:]
        try:
            self.mod.WEB_ROOT = Path(tempfile.gettempdir())
            self.mod.WEB_REQUIRE_TOKEN = False
            self.mod.normalize_host = lambda host: (None, "token_required")
            os.sys.argv = ["web_server.py", "--host", "0.0.0.0", "--port", "0"]
            code = self.mod.main()
            self.assertEqual(code, 2)
        finally:
            self.mod.WEB_ROOT = old_root
            self.mod.WEB_REQUIRE_TOKEN = old_require
            self.mod.normalize_host = old_normalize
            os.sys.argv = old_argv

    def test_respond_notesctl_error_status(self):
        handler = self.build_handler()
        old_json = self.mod.run_notesctl_json
        old_raw = self.mod.run_notesctl_command
        try:
            self.mod.run_notesctl_json = lambda command_name, timeout, extra_env=None, options=None: {"ok": False, "error": "fail"}
            self.mod.run_notesctl_command = lambda command_name, timeout, extra_env=None, options=None: {"ok": False, "error": "fail"}
            handler.respond_notesctl_json("status_json")
            self.assertEqual(handler._status, 500)
            handler.respond_notesctl_raw("run_no_status", 1)
            self.assertEqual(handler._status, 500)
        finally:
            self.mod.run_notesctl_json = old_json
            self.mod.run_notesctl_command = old_raw

    def test_handle_action_branches(self):
        handler = self.build_handler()
        calls = []

        def fake_raw(command_name, timeout=None, extra_env=None, options=None):
            calls.append(("raw", command_name, options or {}, extra_env))
            return handler.respond_json({"ok": True, "command": command_name, "options": options or {}})

        def fake_json(command_name, extra_env=None, options=None):
            calls.append(("json", command_name, options or {}, extra_env))
            return handler.respond_json({"ok": True, "command": command_name, "options": options or {}})

        handler.respond_notesctl_raw = fake_raw
        handler.respond_notesctl_json = fake_json

        def run_action(path, payload):
            handler.wfile = io.BytesIO()
            data = json.dumps(payload).encode("utf-8")
            handler.rfile = io.BytesIO(data)
            handler.headers = {"Content-Length": str(len(data))}
            handler.handle_action(urlparse(path))
            return json.loads(handler.wfile.getvalue().decode("utf-8"))

        # basic action branches
        run_action("/api/run", {})
        run_action("/api/setup", {})
        run_action("/api/verify", {})
        run_action("/api/fix", {})
        run_action("/api/self-heal", {})
        run_action("/api/ensure", {})
        run_action("/api/permissions", {})

        # rotate-logs valid scope
        run_action("/api/rotate-logs", {"scope": "stdout"})
        run_action("/api/rotate-logs", {"scope": "all"})

        # rotate-logs invalid scope
        handler.wfile = io.BytesIO()
        data = json.dumps({"scope": "bad"}).encode("utf-8")
        handler.rfile = io.BytesIO(data)
        handler.headers = {"Content-Length": str(len(data))}
        handler.handle_action(urlparse("/api/rotate-logs"))
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(handler._status, 400)
        self.assertEqual(body.get("error"), "invalid_scope")

        # install with minutes
        run_action("/api/install", {"minutes": 15, "load": True, "web": False})
        # install with interval
        run_action("/api/install", {"interval_sec": 120, "unload": True, "web": True})
        # install defaults
        run_action("/api/install", {})

        # update-vendor valid
        run_action("/api/update-vendor", {"ref": "v1.2.3", "commit": True, "dry_run": True})

        # update-vendor invalid ref
        handler.wfile = io.BytesIO()
        data = json.dumps({"ref": "bad ref"}).encode("utf-8")
        handler.rfile = io.BytesIO(data)
        handler.headers = {"Content-Length": str(len(data))}
        handler.handle_action(urlparse("/api/update-vendor"))
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(handler._status, 400)
        self.assertEqual(body.get("error"), "invalid_ref")

        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir)
            (log_dir / "stdout.log").write_text("hello\n", encoding="utf-8")
            old_log = os.environ.get("NOTES_SNAPSHOT_LOG_DIR")
            try:
                os.environ["NOTES_SNAPSHOT_LOG_DIR"] = str(log_dir)
                run_action("/api/logs", {"type": "stdout", "tail": 1})
                run_action("/api/logs", {"type": "stdout", "since_min": 1})
                handler.wfile = io.BytesIO()
                data = json.dumps({"type": "stderr", "since_min": 1}).encode("utf-8")
                handler.rfile = io.BytesIO(data)
                handler.headers = {"Content-Length": str(len(data))}
                handler.handle_action(urlparse("/api/logs"))
                body = json.loads(handler.wfile.getvalue().decode("utf-8"))
                self.assertEqual(handler._status, 500)
                self.assertEqual(body.get("error"), "read_failed")
            finally:
                if old_log is not None:
                    os.environ["NOTES_SNAPSHOT_LOG_DIR"] = old_log
                elif "NOTES_SNAPSHOT_LOG_DIR" in os.environ:
                    del os.environ["NOTES_SNAPSHOT_LOG_DIR"]

        # invalid log type
        handler.wfile = io.BytesIO()
        data = json.dumps({"type": "nope"}).encode("utf-8")
        handler.rfile = io.BytesIO(data)
        handler.headers = {"Content-Length": str(len(data))}
        handler.handle_action(urlparse("/api/logs"))
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(handler._status, 400)
        self.assertEqual(body.get("error"), "invalid_log_type")

        # unknown action
        handler.wfile = io.BytesIO()
        data = json.dumps({}).encode("utf-8")
        handler.rfile = io.BytesIO(data)
        handler.headers = {"Content-Length": str(len(data))}
        handler.handle_action(urlparse("/api/unknown-action"))
        body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(handler._status, 404)
        self.assertEqual(body.get("error"), "not_found")

        # verify expected args captured
        raw_calls = [(command_name, options) for kind, command_name, options, _ in calls if kind == "raw"]
        json_calls = [(command_name, options) for kind, command_name, options, _ in calls if kind == "json"]
        self.assertIn(("run_no_status", {}), raw_calls)
        self.assertIn(("setup", {}), raw_calls)
        self.assertIn(("verify", {}), raw_calls)
        self.assertIn(("fix", {}), raw_calls)
        self.assertIn(("self_heal", {}), raw_calls)
        self.assertIn(("permissions", {}), raw_calls)
        self.assertIn(("rotate_logs", {"scope": "stdout"}), raw_calls)
        self.assertIn(("rotate_logs", {"scope": "all"}), raw_calls)
        self.assertIn(("ensure_json", {}), json_calls)
        self.assertIn(("update_vendor_commit", {"ref": "v1.2.3", "dry_run": True}), raw_calls)
        self.assertIn(("install", {"minutes": 0, "interval_sec": 0, "load": False, "unload": False, "web": True}), raw_calls)
        for _, _, _, extra_env in calls:
            self.assertIsNotNone(extra_env)
            self.assertTrue(extra_env.get("NOTES_SNAPSHOT_TRIGGER_SOURCE", "").startswith("web:"))

    def test_handle_api_branches(self):
        handler = self.build_handler()
        handler.respond_notesctl_json = lambda command_name, extra_env=None, options=None: handler.respond_json({"ok": True, "command": command_name, "options": options or {}})

        handler.handle_api(urlparse("/api/health"))
        self.assertEqual(handler._status, 200)

        handler.handle_api(urlparse("/api/status"))
        self.assertEqual(handler._status, 200)

        captured = []
        def capture_json(command_name, extra_env=None, options=None):
            captured.append((command_name, options or {}))
            return handler.respond_json({"ok": True, "command": command_name, "options": options or {}})
        handler.respond_notesctl_json = capture_json
        handler.handle_api(urlparse("/api/log-health?tail=50000"))
        self.assertEqual(handler._status, 200)
        self.assertTrue(captured)
        self.assertEqual(captured[-1][0], "log_health_json")
        self.assertEqual(captured[-1][1]["tail"], self.mod.MAX_TAIL_LINES)
        self.assertTrue(any("X-Content-Type-Options" == k for k, _ in handler._headers))
        self.assertTrue(any("X-Frame-Options" == k for k, _ in handler._headers))

        handler.handle_api(urlparse("/api/doctor"))
        self.assertEqual(handler._status, 200)

        captured = []

        def capture_json(command_name, extra_env=None, options=None):
            captured.append((command_name, options or {}))
            return handler.respond_json({"ok": True, "data": {"command": command_name, "options": options or {}}})

        handler.respond_notesctl_json = capture_json
        handler.handle_api(urlparse("/api/recent-runs?tail=500"))
        self.assertEqual(handler._status, 200)
        self.assertTrue(captured)
        self.assertEqual(captured[-1][0], "aggregate_json")
        self.assertEqual(captured[-1][1]["tail"], 200)

        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            old_log = os.environ.get("NOTES_SNAPSHOT_LOG_DIR")
            old_state = os.environ.get("NOTES_SNAPSHOT_STATE_DIR")
            try:
                os.environ["NOTES_SNAPSHOT_LOG_DIR"] = str(Path(tmpdir))
                os.environ["NOTES_SNAPSHOT_STATE_DIR"] = str(state_dir)
                handler.handle_api(urlparse("/api/metrics?tail=1"))
                self.assertEqual(handler._status, 500)
            finally:
                if old_log is not None:
                    os.environ["NOTES_SNAPSHOT_LOG_DIR"] = old_log
                elif "NOTES_SNAPSHOT_LOG_DIR" in os.environ:
                    del os.environ["NOTES_SNAPSHOT_LOG_DIR"]
                if old_state is not None:
                    os.environ["NOTES_SNAPSHOT_STATE_DIR"] = old_state
                elif "NOTES_SNAPSHOT_STATE_DIR" in os.environ:
                    del os.environ["NOTES_SNAPSHOT_STATE_DIR"]

        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "metrics.jsonl").write_text("{\"event\": \"run\"}\n", encoding="utf-8")
            old_log = os.environ.get("NOTES_SNAPSHOT_LOG_DIR")
            old_state = os.environ.get("NOTES_SNAPSHOT_STATE_DIR")
            try:
                os.environ["NOTES_SNAPSHOT_LOG_DIR"] = str(Path(tmpdir))
                os.environ["NOTES_SNAPSHOT_STATE_DIR"] = str(state_dir)
                handler.handle_api(urlparse("/api/metrics?tail=1"))
                self.assertEqual(handler._status, 200)
            finally:
                if old_log is not None:
                    os.environ["NOTES_SNAPSHOT_LOG_DIR"] = old_log
                elif "NOTES_SNAPSHOT_LOG_DIR" in os.environ:
                    del os.environ["NOTES_SNAPSHOT_LOG_DIR"]
                if old_state is not None:
                    os.environ["NOTES_SNAPSHOT_STATE_DIR"] = old_state
                elif "NOTES_SNAPSHOT_STATE_DIR" in os.environ:
                    del os.environ["NOTES_SNAPSHOT_STATE_DIR"]

        handler.handle_api(urlparse("/api/unknown"))
        self.assertEqual(handler._status, 404)

    def test_do_get_and_post(self):
        handler = self.build_handler()
        handler.path = "/api/health"
        handler.do_GET()
        self.assertEqual(handler._status, 200)

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            (temp_root / "index.html").write_text("hello", encoding="utf-8")
            old_root = self.mod.WEB_ROOT
            try:
                self.mod.WEB_ROOT = temp_root
                handler.path = "/"
                handler.do_GET()
                self.assertEqual(handler._status, 200)
            finally:
                self.mod.WEB_ROOT = old_root

        handler.respond_notesctl_raw = lambda command_name, timeout=None, extra_env=None, options=None: handler.respond_json({"ok": True})
        handler.path = "/api/run"
        handler.rfile = io.BytesIO(b"{}")
        handler.headers = {"Content-Length": "2"}
        handler.do_POST()
        self.assertEqual(handler._status, 200)

        handler.path = "/not-api"
        handler.do_POST()
        self.assertEqual(handler._status, 405)


if __name__ == "__main__":
    unittest.main()
