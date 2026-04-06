import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


def write_message(stdin, payload):
    body = json.dumps(payload).encode("utf-8")
    stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    stdin.write(body)
    stdin.flush()


def read_message(stdout):
    content_length = None
    while True:
        line = stdout.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        if line.lower().startswith(b"content-length:"):
            content_length = int(line.split(b":", 1)[1].strip())
    if content_length is None:
        return None
    body = stdout.read(content_length)
    return json.loads(body.decode("utf-8"))


def read_raw_json_line(stdout):
    line = stdout.readline()
    if not line:
        return None
    return json.loads(line.decode("utf-8"))


class MCPServerUnitTests(unittest.TestCase):
    def start_server(self, extra_env=None):
        repo_root = Path(__file__).resolve().parents[2]
        env = os.environ.copy()
        env.update(extra_env or {})
        return subprocess.Popen(
            [str(repo_root / "notesctl"), "mcp"],
            cwd=str(repo_root),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def initialize(self, proc):
        write_message(
            proc.stdin,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "unit-test", "version": "1.0.0"},
                },
            },
        )
        response = read_message(proc.stdout)
        self.assertEqual(response["result"]["protocolVersion"], "2025-03-26")
        write_message(
            proc.stdin,
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
        )

    def stop_server(self, proc):
        for stream_name in ("stdin", "stdout", "stderr"):
            stream = getattr(proc, stream_name, None)
            if stream is not None and not stream.closed:
                stream.close()
        proc.terminate()
        proc.wait(timeout=5)

    def test_stdio_handshake_tools_and_resources(self):
        proc = self.start_server()
        try:
            self.initialize(proc)

            write_message(proc.stdin, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            tools_response = read_message(proc.stdout)
            tool_names = {tool["name"] for tool in tools_response["result"]["tools"]}
            self.assertIn("get_status", tool_names)
            self.assertIn("run_doctor", tool_names)
            self.assertIn("verify_freshness", tool_names)
            self.assertIn("get_log_health", tool_names)
            self.assertIn("list_recent_runs", tool_names)
            self.assertIn("get_access_policy", tool_names)

            write_message(proc.stdin, {"jsonrpc": "2.0", "id": 3, "method": "resources/list"})
            resources_response = read_message(proc.stdout)
            uris = {resource["uri"] for resource in resources_response["result"]["resources"]}
            self.assertIn("notes-snapshot://state.json", uris)
            self.assertIn("notes-snapshot://summary.txt", uris)
            self.assertIn("notes-snapshot://recent-runs", uris)
            self.assertIn("notes-snapshot://config-safe-summary", uris)

            write_message(
                proc.stdin,
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {"name": "get_status", "arguments": {}},
                },
            )
            status_response = read_message(proc.stdout)
            self.assertIn("structuredContent", status_response["result"])
            self.assertIn("health_level", status_response["result"]["structuredContent"])

            write_message(
                proc.stdin,
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "resources/read",
                    "params": {"uri": "notes-snapshot://recent-runs"},
                },
            )
            recent_runs_response = read_message(proc.stdout)
            contents = recent_runs_response["result"]["contents"]
            self.assertEqual(contents[0]["mimeType"], "application/json")
            payload = json.loads(contents[0]["text"])
            self.assertIn("summary", payload)

            write_message(
                proc.stdin,
                {
                    "jsonrpc": "2.0",
                    "id": 6,
                    "method": "tools/call",
                    "params": {"name": "unknown_tool", "arguments": {}},
                },
            )
            error_response = read_message(proc.stdout)
            self.assertEqual(error_response["error"]["code"], -32602)
        finally:
            self.stop_server(proc)

    def test_config_safe_summary_resource_redacts_secrets(self):
        proc = self.start_server(
            {
                "NOTES_SNAPSHOT_AI_API_KEY": "super-secret-key",
                "NOTES_SNAPSHOT_AI_ENABLE": "1",
                "NOTES_SNAPSHOT_AI_PROVIDER": "gemini",
                "NOTES_SNAPSHOT_AI_MODEL": "gemini-2.5-flash",
            }
        )
        try:
            self.initialize(proc)
            write_message(
                proc.stdin,
                {
                    "jsonrpc": "2.0",
                    "id": 7,
                    "method": "resources/read",
                    "params": {"uri": "notes-snapshot://config-safe-summary"},
                },
            )
            response = read_message(proc.stdout)
            text = response["result"]["contents"][0]["text"]
            self.assertNotIn("super-secret-key", text)
            payload = json.loads(text)
            self.assertEqual(payload["ai"]["provider"], "gemini")
        finally:
            self.stop_server(proc)

    def test_debug_log_records_inbound_and_outbound_messages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            debug_log = Path(temp_dir) / "mcp-debug.log"
            proc = self.start_server({"NOTES_SNAPSHOT_MCP_DEBUG_LOG": str(debug_log)})
            try:
                self.initialize(proc)
                write_message(proc.stdin, {"jsonrpc": "2.0", "id": 8, "method": "tools/list"})
                _ = read_message(proc.stdout)
            finally:
                self.stop_server(proc)

            text = debug_log.read_text(encoding="utf-8")
            self.assertIn('"method": "initialize"', text)
            self.assertIn('"method": "tools/list"', text)
            self.assertIn('"protocolVersion": "2025-03-26"', text)

    def test_raw_json_initialize_probe_receives_raw_json_response(self):
        proc = self.start_server()
        try:
            raw_initialize = {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {"roots": {}},
                    "clientInfo": {"name": "claude-code", "version": "2.1.72"},
                },
            }
            proc.stdin.write((json.dumps(raw_initialize) + "\n").encode("utf-8"))
            proc.stdin.flush()
            response = read_raw_json_line(proc.stdout)
            self.assertEqual(response["id"], 9)
            self.assertEqual(response["result"]["protocolVersion"], "2025-03-26")
            self.assertEqual(response["result"]["serverInfo"]["name"], "apple-notes-snapshot-mcp")
        finally:
            self.stop_server(proc)


if __name__ == "__main__":
    unittest.main()
