#!/usr/bin/env python3
"""Minimal terminal MCP server over stdio (newline-delimited JSON-RPC)."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import traceback
from typing import Any, Dict, Optional

SERVER_NAME = "local/terminal-mcp"
SERVER_VERSION = "0.1.0"


class MCPError(Exception):
    """Tool-level error."""


def write_message(message: Dict[str, Any]) -> None:
    body = (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def read_message() -> Optional[Dict[str, Any]]:
    line = sys.stdin.buffer.readline()
    if line == b"":
        return None
    line = line.strip()
    if not line:
        return None

    try:
        parsed = json.loads(line.decode("utf-8"))
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


def run_command(args: Dict[str, Any]) -> Dict[str, Any]:
    cmd = args.get("cmd")
    if not isinstance(cmd, str) or not cmd.strip():
        raise MCPError("'cmd' must be a non-empty string")

    workdir = args.get("workdir")
    if workdir is not None:
        if not isinstance(workdir, str) or not workdir.strip():
            raise MCPError("'workdir' must be a non-empty string when provided")
        if not os.path.isdir(workdir):
            raise MCPError(f"Working directory does not exist: {workdir}")

    timeout_sec = args.get("timeout_sec", 30)
    try:
        timeout_sec = float(timeout_sec)
    except (TypeError, ValueError) as exc:
        raise MCPError("'timeout_sec' must be numeric") from exc
    if timeout_sec <= 0:
        raise MCPError("'timeout_sec' must be > 0")

    shell = args.get("shell", "/bin/bash")
    if not isinstance(shell, str) or not shell:
        raise MCPError("'shell' must be a non-empty string")

    env = None
    env_overrides = args.get("env")
    if env_overrides is not None:
        if not isinstance(env_overrides, dict):
            raise MCPError("'env' must be an object when provided")
        env = os.environ.copy()
        for key, value in env_overrides.items():
            env[str(key)] = str(value)

    try:
        completed = subprocess.run(  # noqa: S603
            [shell, "-lc", cmd],  # noqa: S607
            cwd=workdir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        return {
            "cmd": cmd,
            "shell": shell,
            "workdir": workdir or os.getcwd(),
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": cmd,
            "shell": shell,
            "workdir": workdir or os.getcwd(),
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timed_out": True,
            "timeout_sec": timeout_sec,
        }


def tools_schema() -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": "run_command",
                "description": "Execute a shell command and return stdout, stderr, and exit code.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cmd": {"type": "string", "description": "Shell command to execute."},
                        "workdir": {"type": "string", "description": "Optional working directory."},
                        "timeout_sec": {"type": "number", "description": "Command timeout in seconds."},
                        "shell": {"type": "string", "description": "Shell binary path (default /bin/bash)."},
                        "env": {"type": "object", "description": "Optional environment overrides."},
                    },
                    "required": ["cmd"],
                },
            }
        ]
    }


def main() -> int:
    while True:
        message = read_message()
        if message is None:
            continue

        request_id = message.get("id")
        method = message.get("method")

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
                jsonrpc_result(request_id, tools_schema())
                continue

            if method == "resources/list":
                jsonrpc_result(request_id, {"resources": []})
                continue

            if method == "tools/call":
                params = message.get("params") or {}
                name = params.get("name")
                arguments = params.get("arguments") or {}

                if name != "run_command":
                    raise MCPError(f"Unknown tool: {name}")

                result = run_command(arguments)
                jsonrpc_result(
                    request_id,
                    {
                        "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                        "isError": False,
                    },
                )
                continue

            if method == "ping":
                jsonrpc_result(request_id, {})
                continue

            jsonrpc_error(request_id, -32601, f"Method not found: {method}")

        except MCPError as exc:
            jsonrpc_result(
                request_id,
                {"content": [{"type": "text", "text": str(exc)}], "isError": True},
            )
        except Exception as exc:  # pragma: no cover - defensive path
            jsonrpc_error(
                request_id,
                -32603,
                "Internal error",
                {"error": str(exc), "traceback": traceback.format_exc(limit=5)},
            )


if __name__ == "__main__":
    raise SystemExit(main())
