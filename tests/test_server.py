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
    exc: list[BaseException] = []

    def _reader() -> None:
        try:
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
        except Exception as e:  # noqa: BLE001
            exc.append(e)

    t = threading.Thread(target=_reader, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        msg = "LSP server did not respond within timeout"
        raise TimeoutError(msg)
    if exc:
        raise exc[0]
    return result[0]


def _stop(proc: subprocess.Popen[bytes]) -> None:
    """Terminate the server process, killing it if it does not exit promptly."""
    proc.terminate()
    try:
        proc.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


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

            proc.stdin.write(
                _encode_message(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "processId": None,
                            "rootUri": None,
                            "capabilities": {},
                        },
                    }
                )
            )
            proc.stdin.flush()

            response = _read_message(proc.stdout)

            assert response["jsonrpc"] == "2.0"
            assert response["id"] == 1
            assert "result" in response
            assert response["result"]["serverInfo"]["name"] == "sergey"
        finally:
            _stop(proc)

    def test_server_returns_diagnostic_for_violation(self) -> None:
        """Open a document with a violation and verify a diagnostic is published."""
        proc = subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "sergey", "server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            assert proc.stdin is not None
            assert proc.stdout is not None

            # Handshake: initialize → initialized.
            proc.stdin.write(
                _encode_message(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "processId": None,
                            "rootUri": None,
                            "capabilities": {},
                        },
                    }
                )
            )
            proc.stdin.flush()
            _read_message(proc.stdout)  # consume InitializeResult

            proc.stdin.write(
                _encode_message(
                    {"jsonrpc": "2.0", "method": "initialized", "params": {}}
                )
            )
            proc.stdin.flush()

            # Open a document whose source triggers IMP001.
            uri = "file:///test.py"
            source = "from os.path import join\n"
            proc.stdin.write(
                _encode_message(
                    {
                        "jsonrpc": "2.0",
                        "method": "textDocument/didOpen",
                        "params": {
                            "textDocument": {
                                "uri": uri,
                                "languageId": "python",
                                "version": 1,
                                "text": source,
                            }
                        },
                    }
                )
            )
            proc.stdin.flush()

            notification = _read_message(proc.stdout)

            assert notification["method"] == "textDocument/publishDiagnostics"
            assert notification["params"]["uri"] == uri
            diagnostics = notification["params"]["diagnostics"]
            assert len(diagnostics) == 1
            assert diagnostics[0]["source"] == "sergey"
            assert "IMP001" in diagnostics[0]["message"]
        finally:
            _stop(proc)
