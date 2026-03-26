"""Integration test: verify the LSP server starts and responds to requests."""

import json
import subprocess
import sys
import threading
from typing import Any, BinaryIO


def _encode_message(content: dict[str, Any]) -> bytes:
    """Encode a JSON-RPC message with LSP framing."""
    body = json.dumps(content).encode()
    return f"Content-Length: {len(body)}\r\n\r\n".encode() + body


def _read_message(stdout: BinaryIO, timeout: float = 5.0) -> dict[str, Any]:
    """Read one LSP message from stdout, blocking up to *timeout* seconds."""
    result: list[dict[str, Any]] = []

    def _reader() -> None:
        headers: dict[str, str] = {}
        while True:
            line = stdout.readline()
            stripped = line.rstrip(b"\r\n")
            if not stripped:
                break
            key, _, value = stripped.decode().partition(": ")
            headers[key] = value
        content_length = int(headers["Content-Length"])
        body = stdout.read(content_length)
        result.append(json.loads(body))

    t = threading.Thread(target=_reader, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        msg = "LSP server did not respond within timeout"
        raise TimeoutError(msg)
    return result[0]


class TestLspServer:
    def test_server_responds_to_initialize(self) -> None:
        """Start the LSP server and verify it responds to an initialize request."""
        proc = subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "sergey", "server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            assert proc.stdin is not None
            assert proc.stdout is not None

            initialize_request: dict[str, Any] = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "processId": None,
                    "rootUri": None,
                    "capabilities": {},
                },
            }
            proc.stdin.write(_encode_message(initialize_request))
            proc.stdin.flush()

            response = _read_message(proc.stdout)

            assert response["jsonrpc"] == "2.0"
            assert response["id"] == 1
            assert "result" in response
            assert response["result"]["serverInfo"]["name"] == "sergey"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
