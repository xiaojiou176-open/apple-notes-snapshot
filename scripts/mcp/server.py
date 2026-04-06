#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NOTESCTL = REPO_ROOT / "notesctl"
PROTOCOL_VERSION = "2025-03-26"
SERVER_INFO = {
    "name": "apple-notes-snapshot-mcp",
    "version": "0.1.0",
}
DEFAULT_TAIL = 5
def debug_log(line: str) -> None:
    debug_log_path = os.getenv("NOTES_SNAPSHOT_MCP_DEBUG_LOG", "").strip()
    if not debug_log_path:
        return
    try:
        log_path = Path(debug_log_path)
        if log_path.parent != Path("."):
            log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        # Debug tracing must never break the MCP transport itself.
        return


def env_default(name: str, default: str) -> str:
    return os.getenv(name, default)


def safe_int(raw: str, default: int) -> int:
    try:
        return int(raw)
    except Exception:
        return default


def resolve_notesctl() -> Path:
    override = os.getenv("NOTES_SNAPSHOT_MCP_NOTESCTL", "").strip()
    if override:
        return Path(override)
    return DEFAULT_NOTESCTL


def run_notesctl(command: list[str], timeout_sec: int = 15) -> tuple[dict[str, Any], str | None]:
    notesctl = resolve_notesctl()
    env = os.environ.copy()
    try:
        result = subprocess.run(
            [str(notesctl), *command],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
            env=env,
        )
    except Exception as exc:
        return {}, f"subprocess_failed:{exc}"

    payload = {
        "returncode": result.returncode,
        "stdout": (result.stdout or "").strip(),
        "stderr": (result.stderr or "").strip(),
    }
    if result.returncode != 0:
        return payload, f"command_failed:{' '.join(command)}:{result.returncode}"
    return payload, None


def run_notesctl_json(command: list[str], timeout_sec: int = 15) -> tuple[dict[str, Any], str | None]:
    result, error = run_notesctl(command, timeout_sec)
    if error:
        return result, error
    try:
        data = json.loads(result.get("stdout", ""))
        return data, None
    except Exception as exc:
        return result, f"invalid_json:{' '.join(command)}:{exc}"


def safe_runtime_config_summary() -> dict[str, Any]:
    doctor, _ = run_notesctl_json(["doctor", "--json"])
    audit, _ = run_notesctl_json(["audit", "--json"])
    return {
        "root_dir": doctor.get("root_dir", ""),
        "log_dir": doctor.get("log_dir", ""),
        "state_dir": doctor.get("state_dir", ""),
        "lock_dir": doctor.get("lock_dir", ""),
        "interval_minutes": doctor.get("interval_minutes", ""),
        "timeout_sec": doctor.get("timeout_sec", ""),
        "web": {
            "require_token": ((audit.get("config") or {}).get("require_token", "")),
            "require_token_for_static": ((audit.get("config") or {}).get("require_token_for_static", "")),
            "allow_remote": ((audit.get("config") or {}).get("allow_remote", "")),
            "allow_ips": ((audit.get("config") or {}).get("allow_ips", "")),
            "token_scopes": ((audit.get("config") or {}).get("token_scopes", "")),
            "actions_allow": ((audit.get("config") or {}).get("actions_allow", "")),
            "readonly": ((audit.get("config") or {}).get("readonly", "")),
        },
        "ai": {
            "enabled": env_default("NOTES_SNAPSHOT_AI_ENABLE", "0"),
            "provider": env_default("NOTES_SNAPSHOT_AI_PROVIDER", ""),
            "model": env_default("NOTES_SNAPSHOT_AI_MODEL", ""),
            "allow_note_content": env_default("NOTES_SNAPSHOT_AI_ALLOW_NOTE_CONTENT", "0"),
        },
    }


def resource_state_json() -> dict[str, Any]:
    doctor, _ = run_notesctl_json(["doctor", "--json"])
    state_dir = Path(doctor.get("state_dir", ""))
    state_json = state_dir / "state.json"
    if not state_json.is_file():
        data = {"exists": False, "path": str(state_json), "reason": "state file missing"}
        return {"mimeType": "application/json", "text": json.dumps(data, ensure_ascii=True, indent=2)}
    return {"mimeType": "application/json", "text": state_json.read_text(encoding="utf-8")}


def resource_summary_txt() -> dict[str, Any]:
    doctor, _ = run_notesctl_json(["doctor", "--json"])
    state_dir = Path(doctor.get("state_dir", ""))
    summary_txt = state_dir / "summary.txt"
    if not summary_txt.is_file():
        return {"mimeType": "text/plain", "text": "(missing)\n"}
    return {"mimeType": "text/plain", "text": summary_txt.read_text(encoding="utf-8")}


def resource_recent_runs() -> dict[str, Any]:
    tail = safe_int(env_default("NOTES_SNAPSHOT_MCP_DEFAULT_TAIL", str(DEFAULT_TAIL)), DEFAULT_TAIL)
    aggregate, error = run_notesctl_json(["aggregate", "--tail", str(max(tail, 1)), "--pretty"])
    if error:
        return {
            "mimeType": "application/json",
            "text": json.dumps({"ok": False, "error": error}, ensure_ascii=True, indent=2),
        }
    return {"mimeType": "application/json", "text": json.dumps(aggregate, ensure_ascii=True, indent=2)}


def resource_config_safe_summary() -> dict[str, Any]:
    data = safe_runtime_config_summary()
    return {"mimeType": "application/json", "text": json.dumps(data, ensure_ascii=True, indent=2)}


RESOURCE_READERS = {
    "notes-snapshot://state.json": resource_state_json,
    "notes-snapshot://summary.txt": resource_summary_txt,
    "notes-snapshot://recent-runs": resource_recent_runs,
    "notes-snapshot://config-safe-summary": resource_config_safe_summary,
}


TOOLS = {
    "get_status": {
        "description": "Return the current notesctl status JSON payload.",
        "schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "run_doctor": {
        "description": "Return the current notesctl doctor JSON payload.",
        "schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "verify_freshness": {
        "description": "Run notesctl verify and return its deterministic freshness result.",
        "schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "get_log_health": {
        "description": "Return log-health JSON for the requested tail length.",
        "schema": {
            "type": "object",
            "properties": {
                "tail": {"type": "integer", "minimum": 1, "maximum": 2000},
            },
            "additionalProperties": False,
        },
    },
    "list_recent_runs": {
        "description": "Return recent run summaries aggregated by run_id.",
        "schema": {
            "type": "object",
            "properties": {
                "tail": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "additionalProperties": False,
        },
    },
    "get_access_policy": {
        "description": "Return the current notesctl audit JSON payload for the local Web/access surface.",
        "schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}


RESOURCES = [
    {
        "uri": "notes-snapshot://state.json",
        "name": "Current state.json",
        "description": "Current canonical run record, or a missing-file wrapper when no state file exists yet.",
        "mimeType": "application/json",
    },
    {
        "uri": "notes-snapshot://summary.txt",
        "name": "Current summary.txt",
        "description": "Current plain-text run summary, or a missing sentinel when it is absent.",
        "mimeType": "text/plain",
    },
    {
        "uri": "notes-snapshot://recent-runs",
        "name": "Recent runs summary",
        "description": "Aggregate of recent runs plus summary counts and top failure reason.",
        "mimeType": "application/json",
    },
    {
        "uri": "notes-snapshot://config-safe-summary",
        "name": "Runtime config safe summary",
        "description": "Current safe runtime summary without API keys or bearer tokens.",
        "mimeType": "application/json",
    },
]


def tool_text_and_structured(content: Any) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(content, ensure_ascii=True, indent=2),
            }
        ],
        "structuredContent": content,
        "isError": False,
    }


def handle_tool_call(name: str, arguments: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if name == "get_status":
        data, error = run_notesctl_json(["status", "--json"])
        if error:
            return None, jsonrpc_error(None, -32001, "status_command_failed", {"error": error, "result": data})
        return tool_text_and_structured(data), None

    if name == "run_doctor":
        data, error = run_notesctl_json(["doctor", "--json"])
        if error:
            return None, jsonrpc_error(None, -32002, "doctor_command_failed", {"error": error, "result": data})
        return tool_text_and_structured(data), None

    if name == "verify_freshness":
        data, error = run_notesctl(["verify"])
        if error:
            content = {
                "ok": False,
                "returncode": data.get("returncode"),
                "stdout": data.get("stdout", ""),
                "stderr": data.get("stderr", ""),
            }
            return tool_text_and_structured(content), None
        content = {
            "ok": True,
            "returncode": data.get("returncode"),
            "stdout": data.get("stdout", ""),
            "stderr": data.get("stderr", ""),
        }
        return tool_text_and_structured(content), None

    if name == "get_log_health":
        tail = safe_int(str(arguments.get("tail", DEFAULT_TAIL)), DEFAULT_TAIL)
        data, error = run_notesctl_json(["log-health", "--json", "--tail", str(tail)])
        if error:
            return None, jsonrpc_error(None, -32003, "log_health_failed", {"error": error, "result": data})
        return tool_text_and_structured(data), None

    if name == "list_recent_runs":
        tail = safe_int(str(arguments.get("tail", env_default("NOTES_SNAPSHOT_MCP_DEFAULT_TAIL", str(DEFAULT_TAIL)))), DEFAULT_TAIL)
        data, error = run_notesctl_json(["aggregate", "--tail", str(max(tail, 1))])
        if error:
            return None, jsonrpc_error(None, -32004, "aggregate_failed", {"error": error, "result": data})
        return tool_text_and_structured(data), None

    if name == "get_access_policy":
        data, error = run_notesctl_json(["audit", "--json"])
        if error:
            return None, jsonrpc_error(None, -32005, "audit_failed", {"error": error, "result": data})
        return tool_text_and_structured(data), None

    return None, jsonrpc_error(None, -32602, "unknown_tool", {"tool": name})


def jsonrpc_success(id_value: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_value, "result": result}


def jsonrpc_error(id_value: Any, code: int, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": id_value,
        "error": {"code": code, "message": message},
    }
    if data is not None:
        payload["error"]["data"] = data
    return payload


def write_message(payload: dict[str, Any], transport: str) -> None:
    serialized = json.dumps(payload, ensure_ascii=True)
    debug_log(f"OUT {serialized}")
    encoded = serialized.encode("utf-8")
    if transport == "raw":
        sys.stdout.buffer.write(encoded + b"\n")
    else:
        sys.stdout.buffer.write(f"Content-Length: {len(encoded)}\r\n\r\n".encode("ascii"))
        sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def read_message() -> tuple[dict[str, Any] | None, str]:
    content_length = None
    first_line = sys.stdin.buffer.readline()
    if not first_line:
        return None, "framed"

    stripped = first_line.strip()
    if stripped.startswith(b"{"):
        raw_text = first_line.decode("utf-8", errors="replace")
        try:
            message = json.loads(raw_text)
        except Exception as exc:
            debug_log(f"IN parse error: {exc}; raw={raw_text}")
            raise
        debug_log(f"IN {json.dumps(message, ensure_ascii=True)}")
        return message, "raw"

    while True:
        line = first_line if content_length is None else sys.stdin.buffer.readline()
        first_line = b""
        if not line:
            return None, "framed"
        if line in (b"\r\n", b"\n"):
            break
        if line.lower().startswith(b"content-length:"):
            try:
                content_length = int(line.split(b":", 1)[1].strip())
            except Exception:
                return None, "framed"
    if content_length is None:
        return None, "framed"
    body = sys.stdin.buffer.read(content_length)
    if not body:
        return None, "framed"
    raw_text = body.decode("utf-8", errors="replace")
    try:
        message = json.loads(raw_text)
    except Exception as exc:
        debug_log(f"IN parse error: {exc}; raw={raw_text}")
        raise
    debug_log(f"IN {json.dumps(message, ensure_ascii=True)}")
    return message, "framed"


def handle_request(message: dict[str, Any], initialized: bool) -> tuple[dict[str, Any] | None, bool]:
    method = message.get("method")
    id_value = message.get("id")

    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
            },
            "serverInfo": SERVER_INFO,
        }
        return jsonrpc_success(id_value, result), initialized

    if method == "notifications/initialized":
        return None, True

    if method == "ping":
        return jsonrpc_success(id_value, {}), initialized

    if not initialized:
        return jsonrpc_error(id_value, -32000, "server_not_initialized"), initialized

    if method == "tools/list":
        tools = []
        for tool_name, item in TOOLS.items():
            tools.append(
                {
                    "name": tool_name,
                    "description": item["description"],
                    "inputSchema": item["schema"],
                    "annotations": {"readOnlyHint": True},
                }
            )
        return jsonrpc_success(id_value, {"tools": tools}), initialized

    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name", "")
        arguments = params.get("arguments") or {}
        result, error = handle_tool_call(name, arguments)
        if error:
            error["id"] = id_value
            return error, initialized
        return jsonrpc_success(id_value, result), initialized

    if method == "resources/list":
        return jsonrpc_success(id_value, {"resources": RESOURCES}), initialized

    if method == "resources/read":
        params = message.get("params") or {}
        uri = params.get("uri", "")
        reader = RESOURCE_READERS.get(uri)
        if reader is None:
            return jsonrpc_error(id_value, -32602, "unknown_resource", {"uri": uri}), initialized
        content = reader()
        result = {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": content["mimeType"],
                    "text": content["text"],
                }
            ]
        }
        return jsonrpc_success(id_value, result), initialized

    return jsonrpc_error(id_value, -32601, "method_not_found", {"method": method}), initialized


def main() -> int:
    initialized = False
    transport = "framed"
    while True:
        message, transport = read_message()
        if message is None:
            return 0
        response, initialized = handle_request(message, initialized)
        if response is not None:
            write_message(response, transport)


if __name__ == "__main__":
    raise SystemExit(main())
