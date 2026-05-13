"""Minimal MCP-over-HTTP JSON-RPC 2.0 mock server for /verify-slice P02-S07-T001.

Implements MCP §6.1 lifecycle + discovery methods:
  - initialize                  → returns protocolVersion + capabilities
  - notifications/initialized   → 202 accepted (notification, no id)
  - tools/list                  → returns 1 tool with input_schema
  - resources/list              → returns 1 resource
  - prompts/list                → returns 1 prompt
  - everything else             → -32601 method not found

Bound to 127.0.0.1:8080 by default.
Run: python3 mcp_mock_server.py
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PROTOCOL_VERSION = "2025-06-18"

TOOLS = [
    {
        "name": "echo",
        "description": "Returns the input string verbatim. Safe read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    }
]

RESOURCES = [
    {
        "uri": "mcp://sandbox/readme",
        "name": "Sandbox README",
        "mimeType": "text/markdown",
        "description": "Read-only sandbox documentation.",
    }
]

PROMPTS = [
    {
        "name": "summarize",
        "description": "Summarize a piece of text in 1 sentence.",
        "arguments": [{"name": "text", "description": "Text to summarize", "required": True}],
    }
]


class MCPHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # noqa: A003 — stdlib override
        sys.stderr.write("[mcp-mock %s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _json(self, status: int, body: dict | None) -> None:
        payload = b"" if body is None else json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    def do_POST(self) -> None:  # noqa: N802 — stdlib override
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        try:
            req = json.loads(raw) if raw else {}
        except Exception:
            self._json(400, {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}})
            return

        method = req.get("method")
        msg_id = req.get("id")
        is_notification = msg_id is None

        sys.stderr.write(f"[mcp-mock] POST {self.path} method={method} id={msg_id}\n")

        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                "serverInfo": {"name": "mcp-mock-verify-p02s07", "version": "0.1.0"},
            }
            self._json(200, {"jsonrpc": "2.0", "id": msg_id, "result": result})
            return

        if method == "notifications/initialized":
            self._json(202, None)
            return

        if method == "tools/list":
            self._json(200, {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}})
            return
        if method == "resources/list":
            self._json(200, {"jsonrpc": "2.0", "id": msg_id, "result": {"resources": RESOURCES}})
            return
        if method == "prompts/list":
            self._json(200, {"jsonrpc": "2.0", "id": msg_id, "result": {"prompts": PROMPTS}})
            return

        if is_notification:
            self._json(202, None)
            return
        self._json(
            200,
            {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}},
        )

    def do_GET(self) -> None:  # noqa: N802 — stdlib override
        if self.path in ("/health", "/healthz"):
            self._json(200, {"status": "ok"})
            return
        self._json(404, {"error": "use POST for MCP JSON-RPC"})


def main() -> None:
    host = "127.0.0.1"
    port = 8080
    server = HTTPServer((host, port), MCPHandler)
    sys.stderr.write(f"[mcp-mock] listening on http://{host}:{port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
