#!/usr/bin/env python3
import argparse
import ipaddress
import json
import os
import re
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path, PurePosixPath
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlparse, unquote

# ------------------------------
# Helpers
# ------------------------------
def safe_int(value, default):
    try:
        return int(value)
    except Exception:
        return default

def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "y", "on")

def parse_csv(value):
    return web_policy_helpers.parse_csv(value)

# ------------------------------
# Constants
# ------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ops import web_policy_helpers, web_surface_helpers  # noqa: E402

WEB_ROOT = REPO_ROOT / "web"
WEB_NOTESCTL_OVERRIDE = os.getenv("NOTES_SNAPSHOT_WEB_NOTESCTL", "").strip()
NOTESCTL_CANDIDATES = []
if WEB_NOTESCTL_OVERRIDE:
    NOTESCTL_CANDIDATES.append(Path(WEB_NOTESCTL_OVERRIDE))
NOTESCTL_CANDIDATES.extend([REPO_ROOT / "notesctl", REPO_ROOT / "scripts" / "notesctl.zsh"])
DEFAULT_LOG_DIR = str(REPO_ROOT / ".runtime-cache" / "logs" / "apple-notes-snapshot")
DEFAULT_STATE_DIR = str(
    REPO_ROOT / ".runtime-cache" / "cache" / "apple-notes-snapshot" / "state"
)

DEFAULT_HOST = os.getenv("NOTES_SNAPSHOT_WEB_HOST", "127.0.0.1")
DEFAULT_PORT = safe_int(os.getenv("NOTES_SNAPSHOT_WEB_PORT", "8787"), 8787)
DEFAULT_CMD_TIMEOUT = safe_int(os.getenv("NOTES_SNAPSHOT_WEB_CMD_TIMEOUT_SEC", "10"), 10)
WEB_ALLOW_REMOTE = env_bool("NOTES_SNAPSHOT_WEB_ALLOW_REMOTE", False)
WEB_TOKEN = os.getenv("NOTES_SNAPSHOT_WEB_TOKEN", "").strip()
WEB_REQUIRE_TOKEN = env_bool("NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN", True)
WEB_REQUIRE_TOKEN_FOR_STATIC = env_bool("NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN_FOR_STATIC", False)
WEB_READONLY = env_bool("NOTES_SNAPSHOT_WEB_READONLY", False)
WEB_ALLOW_IPS_RAW = os.getenv("NOTES_SNAPSHOT_WEB_ALLOW_IPS", "").strip()
WEB_TOKEN_SCOPES_RAW = os.getenv("NOTES_SNAPSHOT_WEB_TOKEN_SCOPES", "").strip()
WEB_ACTIONS_ALLOW_RAW = os.getenv("NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW", "").strip()
WEB_RATE_LIMIT_WINDOW_SEC = safe_int(os.getenv("NOTES_SNAPSHOT_WEB_RATE_LIMIT_WINDOW_SEC", "60"), 60)
WEB_RATE_LIMIT_MAX = safe_int(os.getenv("NOTES_SNAPSHOT_WEB_RATE_LIMIT_MAX", "120"), 120)
WEB_ACTION_COOLDOWNS_RAW = os.getenv("NOTES_SNAPSHOT_WEB_ACTION_COOLDOWNS", "").strip()
MAX_TAIL_LINES = safe_int(os.getenv("NOTES_SNAPSHOT_WEB_MAX_TAIL_LINES", "2000"), 2000)
MAX_BODY_BYTES = 64 * 1024
ACTION_LOCK = threading.Lock()
if MAX_TAIL_LINES < 1:
    MAX_TAIL_LINES = 1

SAFE_NOTESCTL_ARG_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
SAFE_STATIC_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
STATIC_CONTENT_TYPES = web_surface_helpers.STATIC_CONTENT_TYPES

ACTION_TIMEOUTS = {
    "setup": 420,
    "run": 120,
    "verify": 60,
    "fix": 120,
    "self-heal": 240,
    "install": 90,
    "ensure": 60,
    "update-vendor": 300,
    "rotate-logs": 60,
    "permissions": 20,
    "logs": 20,
}

ALL_SCOPES = {"read", "run", "install", "vendor", "logs", "system"}
ACTION_SCOPES = {
    "run": "run",
    "setup": "run",
    "verify": "run",
    "fix": "run",
    "self-heal": "run",
    "install": "install",
    "ensure": "install",
    "rotate-logs": "logs",
    "update-vendor": "vendor",
    "permissions": "system",
    "logs": "logs",
}
READ_SCOPES = {
    "/api/health": "read",
    "/api/status": "read",
    "/api/log-health": "read",
    "/api/doctor": "read",
    "/api/metrics": "read",
    "/api/recent-runs": "read",
    "/api/access": "read",
}
ALL_ACTIONS = set(ACTION_SCOPES.keys())
DEFAULT_ACTION_COOLDOWNS = {
    "run": 60,
    "install": 60,
    "update-vendor": 300,
}

def parse_allow_ips(raw):
    return web_policy_helpers.parse_allow_ips(raw)

def normalize_client_ip(addr):
    return web_policy_helpers.normalize_client_ip(addr)

def parse_scopes(raw):
    return web_policy_helpers.parse_scopes(raw, ALL_SCOPES)

def parse_action_allowlist(raw):
    return web_policy_helpers.parse_action_allowlist(raw, ALL_ACTIONS)

def parse_action_cooldowns(raw, defaults):
    return web_policy_helpers.parse_action_cooldowns(raw, defaults, ALL_ACTIONS)

def validate_action_scopes(action_allowlist, token_scopes):
    return web_policy_helpers.validate_action_scopes(action_allowlist, token_scopes, ACTION_SCOPES)

ALLOW_IPS, ALLOW_IPS_ERROR = parse_allow_ips(WEB_ALLOW_IPS_RAW)
TOKEN_SCOPES, TOKEN_SCOPES_ERROR = parse_scopes(WEB_TOKEN_SCOPES_RAW)
ACTION_ALLOWLIST, ACTION_ALLOWLIST_ERROR = parse_action_allowlist(WEB_ACTIONS_ALLOW_RAW)
ACTION_SCOPE_MISMATCH_ERROR = validate_action_scopes(ACTION_ALLOWLIST, TOKEN_SCOPES)
ACTION_COOLDOWNS, ACTION_COOLDOWNS_ERROR = parse_action_cooldowns(WEB_ACTION_COOLDOWNS_RAW, DEFAULT_ACTION_COOLDOWNS)
RATE_LIMIT_BUCKETS = {}
RATE_LIMIT_LOCK = threading.Lock()
ACTION_LAST_RUN = {}
ACTION_COOLDOWN_LOCK = threading.Lock()

def compute_allowed_actions():
    return web_policy_helpers.compute_allowed_actions(
        WEB_READONLY,
        ACTION_ALLOWLIST,
        ALL_ACTIONS,
        TOKEN_SCOPES,
        ACTION_SCOPES,
    )

def check_rate_limit(client_ip):
    return web_policy_helpers.check_rate_limit(
        client_ip,
        WEB_RATE_LIMIT_MAX,
        WEB_RATE_LIMIT_WINDOW_SEC,
        RATE_LIMIT_BUCKETS,
        RATE_LIMIT_LOCK,
    )

def check_action_cooldown(action):
    return web_policy_helpers.check_action_cooldown(
        action,
        ACTION_COOLDOWNS,
        ACTION_LAST_RUN,
        ACTION_COOLDOWN_LOCK,
    )

def resolve_notesctl():
    for candidate in NOTESCTL_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None

def sanitize_notesctl_args(args):
    safe_args = []
    for arg in args:
        if not isinstance(arg, str):
            return None
        if not arg or not SAFE_NOTESCTL_ARG_RE.fullmatch(arg):
            return None
        safe_args.append(arg)
    return safe_args

def build_notesctl_invocation(command_name, options=None):
    options = dict(options or {})
    env_overrides = {}

    if command_name == "run_no_status":
        return ["run", "--no-status"], env_overrides
    if command_name == "setup":
        return ["setup"], env_overrides
    if command_name == "verify":
        return ["verify"], env_overrides
    if command_name == "fix":
        return ["fix"], env_overrides
    if command_name == "self_heal":
        return ["self-heal"], env_overrides
    if command_name == "permissions":
        return ["permissions"], env_overrides
    if command_name == "status_json":
        return ["status", "--json"], env_overrides
    if command_name == "doctor_json":
        return ["doctor", "--json"], env_overrides
    if command_name == "aggregate_json":
        tail_lines = clamp_int(options.get("tail", 20), 20, 1, 200)
        return ["aggregate", "--tail", str(tail_lines)], env_overrides
    if command_name == "ensure_json":
        return ["ensure", "--json"], env_overrides
    if command_name == "log_health_json":
        tail_lines = clamp_int(options.get("tail", 200), 200, 1, MAX_TAIL_LINES)
        return ["log-health", "--json", "--tail", str(tail_lines)], env_overrides
    if command_name == "rotate_logs":
        allowed = {
            "all": "--all",
            "stdout": "--stdout",
            "stderr": "--stderr",
            "launchd": "--launchd",
            "metrics": "--metrics",
            "webui": "--webui",
            "structured": "--structured",
        }
        flag = allowed.get(options.get("scope", "all"))
        if not flag:
            return None, None
        return ["rotate-logs", flag], env_overrides
    if command_name == "install":
        args = ["install"]
        interval_sec = safe_int(options.get("interval_sec", 0), 0)
        minutes = safe_int(options.get("minutes", 0), 0)
        if interval_sec > 0:
            args += ["--interval", str(interval_sec)]
        elif minutes > 0:
            args += ["--minutes", str(minutes)]
        else:
            args += ["--minutes", "30"]
        if parse_bool(options.get("load", False)):
            args.append("--load")
        if parse_bool(options.get("unload", False)):
            args.append("--unload")
        if parse_bool(options.get("web", True)):
            args.append("--web")
        else:
            args.append("--no-web")
        return args, env_overrides
    if command_name in ("update_vendor", "update_vendor_commit"):
        ref = sanitize_ref((options.get("ref") or "").strip())
        if ref is None:
            return None, None
        if ref:
            env_overrides["NOTES_SNAPSHOT_VENDOR_REF"] = ref
        args = ["update-vendor-commit" if command_name == "update_vendor_commit" else "update-vendor"]
        if parse_bool(options.get("dry_run", False)):
            args.append("--patch-dry-run")
        return args, env_overrides
    return None, None

def run_notesctl_command(command_name, timeout_sec, extra_env=None, options=None):
    script = resolve_notesctl()
    if not script:
        return {"ok": False, "error": "notesctl_not_found"}

    safe_args, invocation_env = build_notesctl_invocation(command_name, options=options)
    if safe_args is None:
        return {"ok": False, "error": "invalid_args"}

    cmd = [str(script)] + safe_args
    if not os.access(script, os.X_OK):
        cmd = ["/bin/zsh", str(script)] + safe_args

    start = time.time()
    env = os.environ.copy()
    env.update(invocation_env)
    if extra_env:
        env.update(extra_env)
    try:
        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
            env=env,
            shell=False,
        )
    except Exception as exc:
        return {"ok": False, "error": "subprocess_failed", "detail": str(exc)}

    elapsed = round(time.time() - start, 2)

    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": (result.stdout or "").strip(),
        "stderr": (result.stderr or "").strip(),
        "duration_sec": elapsed,
    }

def run_notesctl_json(command_name, timeout_sec, extra_env=None, options=None):
    result = run_notesctl_command(command_name, timeout_sec, extra_env=extra_env, options=options)
    if not result.get("ok"):
        return result
    raw = result.get("stdout", "").strip()
    try:
        data = json.loads(raw)
    except Exception as exc:
        return {
            "ok": False,
            "error": "invalid_json",
            "detail": str(exc),
            "raw": raw,
        }
    return {"ok": True, "data": data}

def load_metrics_jsonl(path, tail_lines):
    entries = deque(maxlen=tail_lines)
    errors = 0
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except Exception:
                    errors += 1
    except Exception as exc:
        return {"ok": False, "error": "read_failed", "detail": str(exc)}

    return {"ok": True, "entries": list(entries), "errors": errors}

def tail_file(path, tail_lines):
    lines = deque(maxlen=tail_lines)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                lines.append(line.rstrip("\n"))
    except Exception as exc:
        return {"ok": False, "error": "read_failed", "detail": str(exc)}
    return {"ok": True, "lines": list(lines)}

def filter_since(path, since_minutes, max_lines=MAX_TAIL_LINES):
    cutoff = datetime.now() - timedelta(minutes=since_minutes)
    limit = safe_int(max_lines, MAX_TAIL_LINES)
    if limit < 1:
        limit = 1
    lines = deque(maxlen=limit)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                raw = line.rstrip("\n")
                if len(raw) >= 19 and raw[4] == "-" and raw[7] == "-":
                    ts = raw[:19]
                    try:
                        parsed = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                        if parsed >= cutoff:
                            lines.append(raw)
                    except Exception:
                        lines.append(raw)
                else:
                    lines.append(raw)
    except Exception as exc:
        return {"ok": False, "error": "read_failed", "detail": str(exc)}
    return {"ok": True, "lines": list(lines)}

def sanitize_ref(value):
    return web_policy_helpers.sanitize_ref(value)

def parse_bool(value):
    return web_policy_helpers.parse_bool(value)

def clamp_int(value, default, min_value, max_value):
    return web_policy_helpers.clamp_int(value, default, min_value, max_value, safe_int)

def normalize_static_request_path(raw_path):
    return web_surface_helpers.normalize_static_request_path(raw_path, SAFE_STATIC_PATH_RE)

def build_static_file_index(base_dir):
    return web_surface_helpers.build_static_file_index(base_dir)

def resolve_static_path(base_dir, raw_path):
    return web_surface_helpers.resolve_static_path(base_dir, raw_path, SAFE_STATIC_PATH_RE)

def static_content_type(path):
    return web_surface_helpers.static_content_type(path)

def extract_token_from_request(handler, parsed):
    return web_surface_helpers.extract_token_from_request(handler, parsed)

def normalize_host(host):
    return web_policy_helpers.normalize_host(host, WEB_ALLOW_REMOTE, WEB_TOKEN, WEB_REQUIRE_TOKEN)

def is_ip_allowed(client_ip):
    return web_policy_helpers.is_ip_allowed(client_ip, ALLOW_IPS)

def read_json_body(handler):
    length = safe_int(handler.headers.get("Content-Length", "0"), 0)
    if length <= 0:
        return {}
    if length > MAX_BODY_BYTES:
        raise ValueError("payload_too_large")
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid_json: {exc}") from exc

# ------------------------------
# HTTP Server
# ------------------------------
class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class NotesHandler(BaseHTTPRequestHandler):
    server_version = "NotesSnapshotHTTP/1.0"
    security_headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
    }
    static_csp = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "base-uri 'none'; "
        "frame-ancestors 'none'"
    )

    def log_message(self, format, *args):
        return

    def respond_auth_required(self):
        payload = {"ok": False, "error": "unauthorized"}
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(401)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        for key, value in self.security_headers.items():
            self.send_header(key, value)
        self.send_header("WWW-Authenticate", "Bearer")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def respond_forbidden(self, error, detail=None):
        payload = {"ok": False, "error": error}
        if detail:
            payload["detail"] = detail
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(403)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        for key, value in self.security_headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def respond_rate_limited(self, retry_after):
        payload = {"ok": False, "error": "rate_limited", "retry_after": retry_after}
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(429)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Retry-After", str(retry_after))
        for key, value in self.security_headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def enforce_rate_limit(self):
        retry_after = check_rate_limit(self.client_address[0])
        if retry_after is None:
            return True
        self.respond_rate_limited(retry_after)
        return False

    def require_access(self, parsed, scope):
        if not is_ip_allowed(self.client_address[0]):
            self.respond_forbidden("ip_not_allowed")
            return False
        if WEB_REQUIRE_TOKEN:
            token = extract_token_from_request(self, parsed)
            if not token or token != WEB_TOKEN:
                self.respond_auth_required()
                return False
        if TOKEN_SCOPES is not None and scope not in TOKEN_SCOPES:
            self.respond_forbidden("insufficient_scope", f"required={scope}")
            return False
        return True

    def do_GET(self):
        parsed = urlparse(self.path)
        if not is_ip_allowed(self.client_address[0]):
            self.respond_forbidden("ip_not_allowed")
            return
        if parsed.path.startswith("/api/"):
            if not self.enforce_rate_limit():
                return
            self.handle_api(parsed)
            return
        self.serve_static(parsed)

    def do_POST(self):
        parsed = urlparse(self.path)
        if not is_ip_allowed(self.client_address[0]):
            self.respond_forbidden("ip_not_allowed")
            return
        if parsed.path.startswith("/api/"):
            if not self.enforce_rate_limit():
                return
            self.handle_action(parsed)
            return
        self.respond_json({"ok": False, "error": "method_not_allowed"}, status=405)

    def handle_api(self, parsed):
        scope = READ_SCOPES.get(parsed.path, "read")
        if not self.require_access(parsed, scope):
            return
        plan = web_surface_helpers.build_read_route_plan(
            parsed.path,
            parsed.query,
            max_tail_lines=MAX_TAIL_LINES,
            default_state_dir=DEFAULT_STATE_DIR,
            environ=os.environ,
            clamp_int=clamp_int,
        )
        kind = plan.get("kind")
        if kind == "json":
            return self.respond_json(plan["payload"])
        if kind == "notesctl_json":
            return self.respond_notesctl_json(plan["command"], options=plan.get("options"))
        if kind == "metrics":
            result = load_metrics_jsonl(plan["metrics_path"], plan["tail"])
            if not result.get("ok"):
                return self.respond_json(result, status=500)
            payload = {
                "ok": True,
                "file": plan["metrics_path"],
                "tail": plan["tail"],
                "entries": result["entries"],
                "errors": result["errors"],
            }
            return self.respond_json(payload)
        if kind == "access":
            payload = web_surface_helpers.build_access_payload(
                WEB_REQUIRE_TOKEN,
                WEB_REQUIRE_TOKEN_FOR_STATIC,
                WEB_READONLY,
                TOKEN_SCOPES,
                ACTION_ALLOWLIST,
                ACTION_COOLDOWNS,
                compute_allowed_actions,
                WEB_RATE_LIMIT_WINDOW_SEC,
                WEB_RATE_LIMIT_MAX,
            )
            return self.respond_json(payload)
        return self.respond_json({"ok": False, "error": "not_found"}, status=404)

    def respond_notesctl_json(self, command_name, extra_env=None, options=None):
        timeout_sec = DEFAULT_CMD_TIMEOUT
        result = run_notesctl_json(
            command_name,
            timeout_sec,
            extra_env=extra_env,
            options=options,
        )
        status = 200 if result.get("ok") else 500
        return self.respond_json(result, status=status)

    def respond_notesctl_raw(self, command_name, timeout_sec=None, extra_env=None, options=None):
        timeout = timeout_sec if timeout_sec is not None else DEFAULT_CMD_TIMEOUT
        result = run_notesctl_command(
            command_name,
            timeout,
            extra_env=extra_env,
            options=options,
        )
        status = 200 if result.get("ok") else 500
        return self.respond_json(result, status=status)

    def respond_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        for key, value in self.security_headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_static(self, parsed):
        if WEB_REQUIRE_TOKEN_FOR_STATIC:
            if not self.require_access(parsed, "read"):
                return
        safe_path = resolve_static_path(WEB_ROOT, parsed.path)

        if not safe_path or not safe_path.exists():
            return self.respond_json({"ok": False, "error": "missing_index"}, status=500)

        try:
            with open(safe_path, "rb") as handle:
                data = handle.read()
        except Exception as exc:
            return self.respond_json({"ok": False, "error": "read_failed", "detail": str(exc)}, status=500)

        content_type = static_content_type(safe_path)

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", self.static_csp)
        for key, value in self.security_headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def safe_join(self, base_dir, raw_path):
        try:
            path = normalize_static_request_path(raw_path)
            if not path:
                return None
            base_real = os.path.realpath(str(base_dir))
            target = os.path.realpath(os.path.join(base_real, path))
            if not (target == base_real or target.startswith(base_real + os.sep)):
                return None
            return Path(target)
        except Exception:
            return None

    def handle_action(self, parsed):
        action = parsed.path.replace("/api/", "")
        scope = ACTION_SCOPES.get(action, "run")
        if WEB_READONLY:
            return self.respond_forbidden("readonly")
        if ACTION_ALLOWLIST is not None and action not in ACTION_ALLOWLIST:
            return self.respond_forbidden("action_not_allowed", f"action={action}")
        if not self.require_access(parsed, scope):
            return
        try:
            content_type = (self.headers.get("Content-Type") or "").lower()
            payload = read_json_body(self)
            if content_type and "application/json" not in content_type:
                return self.respond_json({"ok": False, "error": "unsupported_media_type"}, status=415)
        except ValueError as exc:
            return self.respond_json({"ok": False, "error": str(exc)}, status=400)

        timeout = ACTION_TIMEOUTS.get(action, DEFAULT_CMD_TIMEOUT)
        extra_env = {"NOTES_SNAPSHOT_TRIGGER_SOURCE": f"web:{action}"}

        if not ACTION_LOCK.acquire(blocking=False):
            return self.respond_json({"ok": False, "error": "busy"}, status=409)

        try:
            cooldown = check_action_cooldown(action)
            if cooldown is not None:
                return self.respond_json({"ok": False, "error": "cooldown", "retry_after": cooldown}, status=429)
            if action == "run":
                return self.respond_notesctl_raw("run_no_status", timeout, extra_env=extra_env)
            if action == "setup":
                return self.respond_notesctl_raw("setup", timeout, extra_env=extra_env)
            if action == "verify":
                return self.respond_notesctl_raw("verify", timeout, extra_env=extra_env)
            if action == "fix":
                return self.respond_notesctl_raw("fix", timeout, extra_env=extra_env)
            if action == "self-heal":
                return self.respond_notesctl_raw("self_heal", timeout, extra_env=extra_env)
            if action == "ensure":
                return self.respond_notesctl_json("ensure_json", extra_env=extra_env)
            if action == "permissions":
                return self.respond_notesctl_raw("permissions", timeout, extra_env=extra_env)
            if action == "rotate-logs":
                scope = (payload.get("scope") or "all").lower()
                if scope not in ("all", "stdout", "stderr", "launchd", "metrics", "webui", "structured"):
                    return self.respond_json({"ok": False, "error": "invalid_scope"}, status=400)
                return self.respond_notesctl_raw(
                    "rotate_logs",
                    timeout,
                    extra_env=extra_env,
                    options={"scope": scope},
                )
            if action == "install":
                minutes = safe_int(payload.get("minutes", 0), 0)
                interval_sec = safe_int(payload.get("interval_sec", 0), 0)
                load = parse_bool(payload.get("load", False))
                unload = parse_bool(payload.get("unload", False))
                web = parse_bool(payload.get("web", True))
                return self.respond_notesctl_raw(
                    "install",
                    timeout,
                    extra_env=extra_env,
                    options={
                        "minutes": minutes,
                        "interval_sec": interval_sec,
                        "load": load,
                        "unload": unload,
                        "web": web,
                    },
                )
            if action == "update-vendor":
                ref = sanitize_ref(payload.get("ref", "").strip())
                if ref is None:
                    return self.respond_json({"ok": False, "error": "invalid_ref"}, status=400)
                dry_run = parse_bool(payload.get("dry_run", False))
                commit = parse_bool(payload.get("commit", False))
                return self.respond_notesctl_raw(
                    "update_vendor_commit" if commit else "update_vendor",
                    timeout,
                    extra_env=extra_env,
                    options={"ref": ref, "dry_run": dry_run},
                )
            if action == "logs":
                log_dir = os.getenv(
                    "NOTES_SNAPSHOT_LOG_DIR",
                    DEFAULT_LOG_DIR,
                )
                log_type = (payload.get("type") or "stdout").lower()
                tail_lines = clamp_int(payload.get("tail", 200), 200, 1, MAX_TAIL_LINES)
                since_min = safe_int(payload.get("since_min", 0), 0)
                if since_min < 0:
                    since_min = 0
                file_map = {
                    "stdout": os.path.join(log_dir, "stdout.log"),
                    "stderr": os.path.join(log_dir, "stderr.log"),
                    "launchd": os.path.join(log_dir, "launchd.out.log"),
                    "webui": os.path.join(log_dir, "webui.out.log"),
                }
                target = file_map.get(log_type)
                if not target:
                    return self.respond_json({"ok": False, "error": "invalid_log_type"}, status=400)
                if since_min > 0:
                    result = filter_since(target, since_min, tail_lines)
                else:
                    result = tail_file(target, tail_lines)
                if not result.get("ok"):
                    return self.respond_json(result, status=500)
                return self.respond_json({
                    "ok": True,
                    "type": log_type,
                    "file": target,
                    "tail": tail_lines,
                    "since_min": since_min,
                    "lines": result["lines"],
                })
        finally:
            ACTION_LOCK.release()

        return self.respond_json({"ok": False, "error": "not_found"}, status=404)

# ------------------------------
# Entrypoint
# ------------------------------
def main():
    parser = argparse.ArgumentParser(description="Notes Snapshot Web UI")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    if not WEB_ROOT.is_dir():
        print(f"missing web root: {WEB_ROOT}", file=sys.stderr)
        return 1

    if ALLOW_IPS_ERROR:
        print(f"ERROR: invalid NOTES_SNAPSHOT_WEB_ALLOW_IPS ({ALLOW_IPS_ERROR})", file=sys.stderr)
        return 2
    if TOKEN_SCOPES_ERROR:
        print(f"ERROR: invalid NOTES_SNAPSHOT_WEB_TOKEN_SCOPES ({TOKEN_SCOPES_ERROR})", file=sys.stderr)
        return 2
    if ACTION_ALLOWLIST_ERROR:
        print(f"ERROR: invalid NOTES_SNAPSHOT_WEB_ACTIONS_ALLOW ({ACTION_ALLOWLIST_ERROR})", file=sys.stderr)
        return 2
    if ACTION_SCOPE_MISMATCH_ERROR:
        print(f"ERROR: action scopes mismatch ({ACTION_SCOPE_MISMATCH_ERROR})", file=sys.stderr)
        return 2
    if ACTION_COOLDOWNS_ERROR:
        print(f"ERROR: invalid NOTES_SNAPSHOT_WEB_ACTION_COOLDOWNS ({ACTION_COOLDOWNS_ERROR})", file=sys.stderr)
        return 2
    if WEB_RATE_LIMIT_WINDOW_SEC < 0 or WEB_RATE_LIMIT_MAX < 0:
        print("ERROR: NOTES_SNAPSHOT_WEB_RATE_LIMIT_* must be >= 0.", file=sys.stderr)
        return 2
    if WEB_ALLOW_REMOTE and not ALLOW_IPS:
        print("WARN: NOTES_SNAPSHOT_WEB_ALLOW_REMOTE=1 with empty allowlist; consider setting NOTES_SNAPSHOT_WEB_ALLOW_IPS.", file=sys.stderr)

    if WEB_REQUIRE_TOKEN and not WEB_TOKEN:
        print("ERROR: NOTES_SNAPSHOT_WEB_TOKEN is required when NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN=1.", file=sys.stderr)
        return 2
    if WEB_REQUIRE_TOKEN_FOR_STATIC and not WEB_TOKEN:
        print("ERROR: NOTES_SNAPSHOT_WEB_TOKEN is required when NOTES_SNAPSHOT_WEB_REQUIRE_TOKEN_FOR_STATIC=1.", file=sys.stderr)
        return 2

    host, err = normalize_host(args.host)
    if err == "remote_blocked":
        print("WARN: remote bind disabled; forcing 127.0.0.1. Set NOTES_SNAPSHOT_WEB_ALLOW_REMOTE=1 to override.", file=sys.stderr)
    if err == "token_required":
        print("ERROR: NOTES_SNAPSHOT_WEB_TOKEN is required when binding to non-loopback address.", file=sys.stderr)
        return 2

    server = ThreadingHTTPServer((host, args.port), NotesHandler)
    print(f"serving http://{host}:{args.port} (web root: {WEB_ROOT})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
