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
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]

# ------------------------------
# Constants
# ------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
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
STATIC_CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
}

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
    if not raw:
        return [], None
    allow = []
    for entry in parse_csv(raw):
        if entry in ("localhost", "loopback"):
            allow.append(ipaddress.ip_network("127.0.0.1/32"))
            allow.append(ipaddress.ip_network("::1/128"))
            continue
        try:
            allow.append(ipaddress.ip_network(entry, strict=False))
            continue
        except Exception:
            pass
        try:
            addr = ipaddress.ip_address(entry)
            if addr.version == 4:
                allow.append(ipaddress.ip_network(f"{addr}/32"))
            else:
                allow.append(ipaddress.ip_network(f"{addr}/128"))
        except Exception:
            return None, f"invalid_allow_ip:{entry}"
    return allow, None

def normalize_client_ip(addr):
    try:
        ip = ipaddress.ip_address(addr)
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        return ip
    except Exception:
        return None

def parse_scopes(raw):
    scopes = {item.lower() for item in parse_csv(raw)}
    if not scopes or "all" in scopes:
        return None, None
    unknown = sorted(scopes - ALL_SCOPES)
    if unknown:
        return None, f"invalid_scopes:{','.join(unknown)}"
    return scopes, None

def parse_action_allowlist(raw):
    actions = {item.strip().lower() for item in parse_csv(raw)}
    if not actions or "all" in actions:
        return None, None
    unknown = sorted(actions - ALL_ACTIONS)
    if unknown:
        return None, f"invalid_actions:{','.join(unknown)}"
    return actions, None

def parse_action_cooldowns(raw, defaults):
    if not raw:
        return dict(defaults), None
    lowered = raw.strip().lower()
    if lowered in ("0", "off", "none", "disable", "disabled"):
        return {}, None
    cooldowns = {}
    for entry in parse_csv(raw):
        if "=" not in entry:
            return None, f"invalid_cooldown:{entry}"
        action, value = [item.strip().lower() for item in entry.split("=", 1)]
        if action not in ALL_ACTIONS:
            return None, f"invalid_cooldown_action:{action}"
        if not value.isdigit():
            return None, f"invalid_cooldown_value:{entry}"
        sec = int(value)
        if sec < 0:
            return None, f"invalid_cooldown_value:{entry}"
        if sec == 0:
            continue
        cooldowns[action] = sec
    return cooldowns, None

def validate_action_scopes(action_allowlist, token_scopes):
    if action_allowlist is None or token_scopes is None:
        return None
    missing = []
    for action in action_allowlist:
        required = ACTION_SCOPES.get(action)
        if required and required not in token_scopes:
            missing.append(f"{action}:{required}")
    if missing:
        return f"action_scope_mismatch:{','.join(sorted(missing))}"
    return None

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
    if WEB_READONLY:
        return []
    if ACTION_ALLOWLIST is None:
        actions = set(ALL_ACTIONS)
    else:
        actions = set(ACTION_ALLOWLIST)
    if TOKEN_SCOPES is None:
        return sorted(actions)
    allowed = []
    for action in actions:
        required = ACTION_SCOPES.get(action)
        if required and required in TOKEN_SCOPES:
            allowed.append(action)
    return sorted(allowed)

def check_rate_limit(client_ip):
    if WEB_RATE_LIMIT_MAX <= 0 or WEB_RATE_LIMIT_WINDOW_SEC <= 0:
        return None
    now = time.monotonic()
    with RATE_LIMIT_LOCK:
        bucket = RATE_LIMIT_BUCKETS.get(client_ip)
        if bucket is None:
            bucket = deque()
            RATE_LIMIT_BUCKETS[client_ip] = bucket
        cutoff = now - WEB_RATE_LIMIT_WINDOW_SEC
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= WEB_RATE_LIMIT_MAX:
            retry_after = int(max(1, WEB_RATE_LIMIT_WINDOW_SEC - (now - bucket[0])))
            return retry_after
        bucket.append(now)
    return None

def check_action_cooldown(action):
    if not ACTION_COOLDOWNS:
        return None
    cooldown = ACTION_COOLDOWNS.get(action)
    if not cooldown:
        return None
    now = time.monotonic()
    with ACTION_COOLDOWN_LOCK:
        last = ACTION_LAST_RUN.get(action, 0)
        elapsed = now - last if last else None
        if elapsed is not None and elapsed < cooldown:
            return int(max(1, cooldown - elapsed))
        ACTION_LAST_RUN[action] = now
    return None

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
    if not value:
        return ""
    if not re.match(r"^[A-Za-z0-9._/-]+$", value):
        return None
    return value

def parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "on")
    return False

def clamp_int(value, default, min_value, max_value):
    number = safe_int(value, default)
    if number < min_value:
        return min_value
    if number > max_value:
        return max_value
    return number

def normalize_static_request_path(raw_path):
    if raw_path is None:
        return None
    try:
        path = unquote(str(raw_path).split("?", 1)[0].split("#", 1)[0])
    except Exception:
        return None
    if any(char in path for char in ("\x00", "\r", "\n")):
        return None
    path = path.lstrip("/")
    if not path:
        return "index.html"
    if not SAFE_STATIC_PATH_RE.fullmatch(path):
        return None
    pure_path = PurePosixPath(path)
    if pure_path.is_absolute():
        return None
    if any(part in ("", ".", "..") for part in pure_path.parts):
        return None
    return pure_path.as_posix()

def build_static_file_index(base_dir):
    base_path = Path(base_dir)
    if not base_path.is_dir():
        return {}
    base_real = base_path.resolve()
    index = {}
    for path in base_real.rglob("*"):
        if not path.is_file():
            continue
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(base_real).as_posix()
        except ValueError:
            continue
        index[relative] = resolved
    return index

def resolve_static_path(base_dir, raw_path):
    static_index = build_static_file_index(base_dir)
    default_path = static_index.get("index.html")
    relative_path = normalize_static_request_path(raw_path)
    if relative_path is None:
        return default_path
    return static_index.get(relative_path) or default_path

def static_content_type(path):
    return STATIC_CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")

def extract_token_from_request(handler, parsed):
    auth_header = handler.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            return token
    token = handler.headers.get("X-Notes-Token", "").strip()
    if token:
        return token
    params = parse_qs(parsed.query or "")
    return (params.get("token") or [""])[0].strip()

def normalize_host(host):
    value = (host or "").strip()
    if value in ("", "127.0.0.1", "localhost", "::1"):
        return "127.0.0.1", None
    if not WEB_ALLOW_REMOTE:
        return "127.0.0.1", "remote_blocked"
    if WEB_REQUIRE_TOKEN and not WEB_TOKEN:
        return None, "token_required"
    return value, None

def is_ip_allowed(client_ip):
    if not ALLOW_IPS:
        return True
    ip = normalize_client_ip(client_ip)
    if not ip:
        return False
    for network in ALLOW_IPS:
        if ip in network:
            return True
    return False

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
        if parsed.path == "/api/health":
            return self.respond_json({"ok": True})

        if parsed.path == "/api/status":
            return self.respond_notesctl_json("status_json")

        if parsed.path == "/api/log-health":
            params = parse_qs(parsed.query)
            tail_lines = clamp_int(params.get("tail", ["200"])[0], 200, 1, MAX_TAIL_LINES)
            return self.respond_notesctl_json("log_health_json", options={"tail": tail_lines})

        if parsed.path == "/api/doctor":
            return self.respond_notesctl_json("doctor_json")

        if parsed.path == "/api/metrics":
            params = parse_qs(parsed.query)
            tail_lines = clamp_int(params.get("tail", ["120"])[0], 120, 1, MAX_TAIL_LINES)
            log_dir = os.getenv(
                "NOTES_SNAPSHOT_LOG_DIR",
                DEFAULT_LOG_DIR,
            )
            state_dir = os.getenv("NOTES_SNAPSHOT_STATE_DIR", DEFAULT_STATE_DIR)
            metrics_path = os.path.join(state_dir, "metrics.jsonl")

            result = load_metrics_jsonl(metrics_path, tail_lines)
            if not result.get("ok"):
                return self.respond_json(result, status=500)

            payload = {
                "ok": True,
                "file": metrics_path,
                "tail": tail_lines,
                "entries": result["entries"],
                "errors": result["errors"],
            }
            return self.respond_json(payload)

        if parsed.path == "/api/recent-runs":
            params = parse_qs(parsed.query)
            tail_count = clamp_int(params.get("tail", ["20"])[0], 20, 1, 200)
            return self.respond_notesctl_json("aggregate_json", options={"tail": tail_count})

        if parsed.path == "/api/access":
            payload = {
                "ok": True,
                "require_token": WEB_REQUIRE_TOKEN,
                "require_token_for_static": WEB_REQUIRE_TOKEN_FOR_STATIC,
                "readonly": WEB_READONLY,
                "token_scopes": sorted(TOKEN_SCOPES) if TOKEN_SCOPES is not None else ["all"],
                "actions_allowlist": sorted(ACTION_ALLOWLIST) if ACTION_ALLOWLIST is not None else ["all"],
                "actions_effective": compute_allowed_actions(),
                "rate_limit_window_sec": WEB_RATE_LIMIT_WINDOW_SEC,
                "rate_limit_max": WEB_RATE_LIMIT_MAX,
                "action_cooldowns": ACTION_COOLDOWNS,
            }
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
