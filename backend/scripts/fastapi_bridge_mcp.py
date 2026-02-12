#!/usr/bin/env python3
"""Minimal FastAPI <-> MCP bridge over stdio.

This server keeps MCP startup stable and exposes two tools:
- list_endpoints: Reads FastAPI OpenAPI schema and returns discovered routes.
- call_endpoint: Executes HTTP requests against the FastAPI base URL.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

SERVER_NAME = "local/fastapi-bridge"
SERVER_VERSION = "0.1.0"
DEFAULT_OPENAPI_URL = "http://127.0.0.1:8001/openapi.json"
DEFAULT_BASE_URL = "http://127.0.0.1:8001"


class MCPError(Exception):
    """Domain error used for tool-level failures."""


def write_message(message: Dict[str, Any]) -> None:
    # Node MCP stdio transport uses newline-delimited JSON messages.
    body = (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def read_message() -> Optional[Dict[str, Any]]:
    stdin = sys.stdin.buffer

    # Accept newline-delimited JSON-RPC when no Content-Length headers are used.
    first = stdin.read(1)
    while first in (b" ", b"\t", b"\r", b"\n"):
        first = stdin.read(1)
    if first == b"":
        return None

    if first == b"{":
        line = first + stdin.readline()
        try:
            parsed = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    headers: Dict[str, str] = {}
    line = first + stdin.readline()
    while True:
        if line == b"":
            return None
        if line in (b"\r\n", b"\n"):
            break

        try:
            text = line.decode("ascii")
        except UnicodeDecodeError:
            text = ""

        if ":" in text:
            key, value = text.split(":", 1)
            headers[key.strip().lower()] = value.strip()

        line = stdin.readline()

    raw_len = headers.get("content-length")
    if raw_len is None:
        return None

    try:
        content_length = int(raw_len)
    except ValueError:
        return None

    body = stdin.read(content_length)
    if len(body) != content_length:
        return None

    try:
        parsed = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


def jsonrpc_result(request_id: Any, result: Dict[str, Any]) -> None:
    write_message({"jsonrpc": "2.0", "id": request_id, "result": result})


def jsonrpc_error(request_id: Any, code: int, message: str, data: Any = None) -> None:
    payload: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        payload["data"] = data
    write_message({"jsonrpc": "2.0", "id": request_id, "error": payload})


def build_base_url_from_openapi(openapi_url: str) -> str:
    marker = "/openapi.json"
    if openapi_url.endswith(marker):
        return openapi_url[: -len(marker)]
    parsed = urllib.parse.urlparse(openapi_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def decode_http_body(raw: bytes, content_type: str, charset: Optional[str]) -> Any:
    if not raw:
        return None

    text = raw.decode(charset or "utf-8", errors="replace")
    if "application/json" in content_type:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


class FastAPIBridge:
    def __init__(self, openapi_url: str, base_url: str, timeout: float) -> None:
        self.openapi_url = openapi_url
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _fetch_openapi(self) -> Dict[str, Any]:
        request = urllib.request.Request(
            self.openapi_url,
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = response.read()
        except urllib.error.URLError as exc:
            raise MCPError(f"Failed to fetch OpenAPI from {self.openapi_url}: {exc}") from exc

        try:
            parsed = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise MCPError(f"OpenAPI response is not valid JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise MCPError("OpenAPI JSON root must be an object")
        return parsed

    def list_endpoints(self) -> List[Dict[str, Any]]:
        spec = self._fetch_openapi()
        paths = spec.get("paths")
        if not isinstance(paths, dict):
            raise MCPError("OpenAPI schema does not contain a valid 'paths' object")

        endpoints: List[Dict[str, Any]] = []
        allowed_methods = {"get", "post", "put", "patch", "delete", "options", "head"}

        for path, operations in paths.items():
            if not isinstance(path, str) or not isinstance(operations, dict):
                continue
            for method, operation in operations.items():
                if method not in allowed_methods:
                    continue
                if not isinstance(operation, dict):
                    operation = {}
                endpoints.append(
                    {
                        "method": method.upper(),
                        "path": path,
                        "operationId": operation.get("operationId"),
                        "summary": operation.get("summary"),
                    }
                )

        endpoints.sort(key=lambda item: (item["path"], item["method"]))
        return endpoints

    def call_endpoint(
        self,
        method: str,
        path: str,
        query: Optional[Dict[str, Any]] = None,
        json_body: Any = None,
        headers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not method or not isinstance(method, str):
            raise MCPError("'method' must be a non-empty string")
        if not path or not isinstance(path, str):
            raise MCPError("'path' must be a non-empty string")

        normalized_method = method.upper()
        if not path.startswith("/"):
            path = "/" + path

        url = self.base_url + path
        if query:
            if not isinstance(query, dict):
                raise MCPError("'query' must be an object")
            pairs: List[Tuple[str, str]] = []
            for key, value in query.items():
                if value is None:
                    continue
                if isinstance(value, list):
                    for item in value:
                        pairs.append((str(key), str(item)))
                else:
                    pairs.append((str(key), str(value)))
            if pairs:
                url = url + "?" + urllib.parse.urlencode(pairs, doseq=True)

        request_headers: Dict[str, str] = {"Accept": "application/json"}
        if headers:
            if not isinstance(headers, dict):
                raise MCPError("'headers' must be an object")
            for key, value in headers.items():
                request_headers[str(key)] = str(value)

        body: Optional[bytes] = None
        if json_body is not None:
            body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")

        request = urllib.request.Request(url, data=body, headers=request_headers, method=normalized_method)

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                content_type = response.headers.get("Content-Type", "")
                charset = response.headers.get_content_charset()
                return {
                    "status": response.status,
                    "url": response.geturl(),
                    "headers": dict(response.headers.items()),
                    "body": decode_http_body(raw, content_type, charset),
                }
        except urllib.error.HTTPError as exc:
            raw = exc.read() if exc.fp else b""
            content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
            charset = exc.headers.get_content_charset() if exc.headers else None
            return {
                "status": exc.code,
                "url": url,
                "headers": dict(exc.headers.items()) if exc.headers else {},
                "body": decode_http_body(raw, content_type, charset),
            }
        except urllib.error.URLError as exc:
            raise MCPError(f"Request failed: {exc}") from exc


def build_tools_schema() -> List[Dict[str, Any]]:
    return [
        {
            "name": "list_endpoints",
            "description": "Fetch OpenAPI schema and list FastAPI endpoints.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "call_endpoint",
            "description": "Call a FastAPI endpoint by HTTP method/path.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "description": "HTTP method, e.g. GET"},
                    "path": {"type": "string", "description": "Endpoint path, e.g. /documents"},
                    "query": {"type": "object", "description": "Query parameters"},
                    "json": {"description": "JSON body payload"},
                    "headers": {"type": "object", "description": "Optional HTTP headers"},
                },
                "required": ["method", "path"],
            },
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Local FastAPI MCP bridge")
    parser.add_argument("--openapi-url", default=DEFAULT_OPENAPI_URL)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    base_url = args.base_url or build_base_url_from_openapi(args.openapi_url)
    bridge = FastAPIBridge(openapi_url=args.openapi_url, base_url=base_url, timeout=args.timeout)

    while True:
        message = read_message()
        if message is None:
            break

        request_id = message.get("id")
        method = message.get("method")

        # Ignore notifications.
        if request_id is None:
            continue

        try:
            if method == "initialize":
                params = message.get("params") or {}
                protocol_version = params.get("protocolVersion") or "2024-11-05"
                jsonrpc_result(
                    request_id,
                    {
                        "protocolVersion": protocol_version,
                        "capabilities": {"tools": {}, "resources": {}},
                        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    },
                )
                continue

            if method == "tools/list":
                jsonrpc_result(request_id, {"tools": build_tools_schema()})
                continue

            if method == "resources/list":
                jsonrpc_result(
                    request_id,
                    {
                        "resources": [
                            {
                                "uri": "fastapi://openapi",
                                "name": "FastAPI OpenAPI schema",
                                "mimeType": "application/json",
                            }
                        ]
                    },
                )
                continue

            if method == "resources/read":
                params = message.get("params") or {}
                uri = params.get("uri")
                if uri != "fastapi://openapi":
                    raise MCPError(f"Unknown resource URI: {uri}")
                spec = bridge._fetch_openapi()
                jsonrpc_result(
                    request_id,
                    {
                        "contents": [
                            {
                                "uri": "fastapi://openapi",
                                "mimeType": "application/json",
                                "text": json.dumps(spec, ensure_ascii=False),
                            }
                        ]
                    },
                )
                continue

            if method == "tools/call":
                params = message.get("params") or {}
                name = params.get("name")
                arguments = params.get("arguments") or {}

                if name == "list_endpoints":
                    endpoints = bridge.list_endpoints()
                    payload = {
                        "openapi_url": bridge.openapi_url,
                        "base_url": bridge.base_url,
                        "count": len(endpoints),
                        "endpoints": endpoints,
                    }
                    jsonrpc_result(
                        request_id,
                        {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}], "isError": False},
                    )
                    continue

                if name == "call_endpoint":
                    result = bridge.call_endpoint(
                        method=str(arguments.get("method", "")),
                        path=str(arguments.get("path", "")),
                        query=arguments.get("query"),
                        json_body=arguments.get("json"),
                        headers=arguments.get("headers"),
                    )
                    jsonrpc_result(
                        request_id,
                        {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}], "isError": False},
                    )
                    continue

                raise MCPError(f"Unknown tool: {name}")

            if method == "ping":
                jsonrpc_result(request_id, {})
                continue

            jsonrpc_error(request_id, -32601, f"Method not found: {method}")

        except MCPError as exc:
            jsonrpc_result(
                request_id,
                {
                    "content": [{"type": "text", "text": str(exc)}],
                    "isError": True,
                },
            )
        except Exception as exc:  # pragma: no cover - defensive safety
            jsonrpc_error(
                request_id,
                -32603,
                "Internal error",
                {
                    "error": str(exc),
                    "traceback": traceback.format_exc(limit=5),
                },
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
