#!/usr/bin/env python3
import os
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, unquote


STATIC_CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
}


def normalize_static_request_path(raw_path, safe_static_path_re):
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
    if not safe_static_path_re.fullmatch(path):
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


def resolve_static_path(base_dir, raw_path, safe_static_path_re):
    static_index = build_static_file_index(base_dir)
    default_path = static_index.get("index.html")
    relative_path = normalize_static_request_path(raw_path, safe_static_path_re)
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


def build_access_payload(web_require_token, web_require_token_for_static, web_readonly, token_scopes, action_allowlist, action_cooldowns, compute_allowed_actions, rate_limit_window_sec, rate_limit_max):
    return {
        "ok": True,
        "require_token": web_require_token,
        "require_token_for_static": web_require_token_for_static,
        "readonly": web_readonly,
        "token_scopes": sorted(token_scopes) if token_scopes is not None else ["all"],
        "actions_allowlist": sorted(action_allowlist) if action_allowlist is not None else ["all"],
        "actions_effective": compute_allowed_actions(),
        "rate_limit_window_sec": rate_limit_window_sec,
        "rate_limit_max": rate_limit_max,
        "action_cooldowns": action_cooldowns,
    }


def build_read_route_plan(path, query, *, max_tail_lines, default_state_dir, environ, clamp_int):
    if path == "/api/health":
        return {"kind": "json", "payload": {"ok": True}}
    if path == "/api/status":
        return {"kind": "notesctl_json", "command": "status_json"}
    if path == "/api/log-health":
        params = parse_qs(query)
        tail_lines = clamp_int(params.get("tail", ["200"])[0], 200, 1, max_tail_lines)
        return {"kind": "notesctl_json", "command": "log_health_json", "options": {"tail": tail_lines}}
    if path == "/api/doctor":
        return {"kind": "notesctl_json", "command": "doctor_json"}
    if path == "/api/metrics":
        params = parse_qs(query)
        tail_lines = clamp_int(params.get("tail", ["120"])[0], 120, 1, max_tail_lines)
        state_dir = environ.get("NOTES_SNAPSHOT_STATE_DIR", default_state_dir)
        metrics_path = os.path.join(state_dir, "metrics.jsonl")
        return {"kind": "metrics", "tail": tail_lines, "metrics_path": metrics_path}
    if path == "/api/recent-runs":
        params = parse_qs(query)
        tail_count = clamp_int(params.get("tail", ["20"])[0], 20, 1, 200)
        return {"kind": "notesctl_json", "command": "aggregate_json", "options": {"tail": tail_count}}
    if path == "/api/access":
        return {"kind": "access"}
    return {"kind": "not_found"}
