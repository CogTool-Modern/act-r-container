#!/usr/bin/env python3
"""
Small HTTP API for running ACT-R model files by URL.

This server is intended for the Heroku container web process. It talks to the
ACT-R remote interface on the loopback/container network and exposes a normal
HTTP endpoint for clients.
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


MESSAGE_END = "\x04"
MODEL_DIR = Path(os.environ.get("ACTR_MODEL_DOWNLOAD_DIR", "/tmp/actr-models"))
MAX_MODEL_BYTES = int(os.environ.get("ACTR_MAX_MODEL_BYTES", str(256 * 1024)))
MAX_RUN_SECONDS = float(os.environ.get("ACTR_MAX_RUN_SECONDS", "60"))
DEFAULT_RUN_SECONDS = float(os.environ.get("ACTR_DEFAULT_RUN_SECONDS", "5"))
DOWNLOAD_TIMEOUT = float(os.environ.get("ACTR_DOWNLOAD_TIMEOUT", "15"))
REMOTE_TIMEOUT = float(os.environ.get("ACTR_REMOTE_TIMEOUT", "30"))
ALLOW_PRIVATE_URLS = os.environ.get("ACTR_ALLOW_PRIVATE_MODEL_URLS", "").lower() in {
    "1",
    "true",
    "yes",
}


class ActRError(RuntimeError):
    pass


class ModelDownloadError(RuntimeError):
    pass


class ActRRemote:
    def __init__(self, host: str, port: int, name: str):
        self.host = host
        self.port = port
        self._next_id = 1
        self._buffer = ""
        self._commands: dict[str, Any] = {}
        self._socket = socket.create_connection((host, port), timeout=REMOTE_TIMEOUT)
        self._socket.settimeout(REMOTE_TIMEOUT)
        self.call_method("set-name", name)

    def close(self) -> None:
        try:
            self.send("close", request_id=None)
        finally:
            self._socket.close()

    def add_command(self, name: str, handler: Any) -> None:
        self._commands[name] = handler
        self.call_method("add", name, name, "Temporary ACT-R API callback.", True)

    def remove_command(self, name: str) -> None:
        self._commands.pop(name, None)
        self.call_method("remove", name)

    def monitor(self, original: str, monitor: str) -> None:
        self.call_method("monitor", original, monitor)

    def remove_monitor(self, original: str, monitor: str) -> None:
        self.call_method("remove-monitor", original, monitor)

    def evaluate(self, command: str, *params: Any) -> list[Any]:
        return self.call_method("evaluate", command, False, *params)

    def call_method(self, method: str, *params: Any) -> list[Any]:
        message_id = self._next_id
        self._next_id += 1
        self.send(method, *params, request_id=message_id)

        while True:
            response = self.receive()
            if response.get("id") != message_id:
                self.handle_callback(response)
                continue

            error = response.get("error")
            if error:
                raise ActRError(error.get("message", str(error)))

            return response.get("result") or []

    def send(self, method: str, *params: Any, request_id: int | None) -> None:
        payload = {"method": method, "params": list(params), "id": request_id}
        self._socket.sendall((json.dumps(payload) + MESSAGE_END).encode("utf-8"))

    def receive(self) -> dict[str, Any]:
        while MESSAGE_END not in self._buffer:
            try:
                chunk = self._socket.recv(4096)
            except socket.timeout as exc:
                raise ActRError("Timed out waiting for ACT-R remote response.") from exc
            if not chunk:
                raise ActRError("ACT-R closed the remote connection.")
            self._buffer += chunk.decode("utf-8")

        raw_message, self._buffer = self._buffer.split(MESSAGE_END, 1)
        return json.loads(raw_message)

    def handle_callback(self, message: dict[str, Any]) -> None:
        if message.get("method") != "evaluate":
            return

        params = message.get("params") or []
        command_name = params[0] if params else None
        handler = self._commands.get(command_name)
        if not handler:
            self.reply(message.get("id"), None, f"No API callback registered for {command_name!r}.")
            return

        try:
            result = handler(*params[2:])
            self.reply(message.get("id"), [result if result is not None else True], None)
        except Exception as exc:  # pragma: no cover - defensive callback boundary
            self.reply(message.get("id"), None, str(exc))

    def reply(self, message_id: Any, result: Any, error: str | None) -> None:
        payload = {
            "id": message_id,
            "result": result,
            "error": {"message": error} if error else None,
        }
        self._socket.sendall((json.dumps(payload) + MESSAGE_END).encode("utf-8"))


class ActRRunner:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def run_model_url(self, payload: dict[str, Any]) -> dict[str, Any]:
        model_url = payload.get("model_url")
        if not isinstance(model_url, str) or not model_url.strip():
            raise ValueError("Request JSON must include a non-empty model_url string.")

        run_seconds = float(payload.get("run_seconds", DEFAULT_RUN_SECONDS))
        if run_seconds < 0 or run_seconds > MAX_RUN_SECONDS:
            raise ValueError(f"run_seconds must be between 0 and {MAX_RUN_SECONDS:g}.")

        compile_model = bool(payload.get("compile", False))
        real_time = bool(payload.get("real_time", False))
        run_id = str(uuid.uuid4())
        model_path = download_model(model_url, run_id)

        with self._lock:
            return self._run_model(run_id, model_url, model_path, run_seconds, compile_model, real_time)

    def _run_model(
        self,
        run_id: str,
        model_url: str,
        model_path: Path,
        run_seconds: float,
        compile_model: bool,
        real_time: bool,
    ) -> dict[str, Any]:
        trace_lines: list[str] = []
        trace_command = f"api-trace-{run_id}"
        monitors = ["model-trace", "command-trace", "warning-trace", "general-trace"]
        client = ActRRemote(default_actr_host(), default_actr_port(), f"ACT-R API {run_id}")

        def append_trace(line: Any) -> bool:
            trace_lines.append(str(line))
            return True

        phase = "connect"
        started_at = time.time()
        try:
            phase = "trace-setup"
            client.add_command(trace_command, append_trace)
            for monitor in monitors:
                client.monitor(monitor, trace_command)

            phase = "load"
            load_params: list[Any] = [str(model_path)]
            if compile_model:
                load_params.append(True)
            load_result = client.evaluate("load-act-r-model", *load_params)

            models = client.evaluate("mp-models")
            current_model = client.evaluate("current-model")

            phase = "run"
            client.evaluate("reset")
            run_result = client.evaluate("run", run_seconds, real_time)

            return {
                "ok": True,
                "run_id": run_id,
                "model_url": model_url,
                "model_path": str(model_path),
                "models": models[0] if models else [],
                "current_model": current_model[0] if current_model else None,
                "load_result": load_result[0] if load_result else None,
                "run_result": run_result,
                "run_seconds": run_seconds,
                "elapsed_seconds": round(time.time() - started_at, 3),
                "trace": "".join(trace_lines),
                "trace_lines": trace_lines,
            }
        except Exception as exc:
            return {
                "ok": False,
                "run_id": run_id,
                "model_url": model_url,
                "model_path": str(model_path),
                "phase": phase,
                "error": str(exc),
                "elapsed_seconds": round(time.time() - started_at, 3),
                "trace": "".join(trace_lines),
                "trace_lines": trace_lines,
            }
        finally:
            for monitor in monitors:
                try:
                    client.remove_monitor(monitor, trace_command)
                except Exception:
                    pass
            try:
                client.remove_command(trace_command)
            except Exception:
                pass
            client.close()


def default_actr_host() -> str:
    return (
        os.environ.get("ACTR_HOST")
        or read_home_file("act-r-address.txt")
        or socket.gethostbyname(socket.gethostname())
    )


def default_actr_port() -> int:
    return int(os.environ.get("ACTR_PORT") or read_home_file("act-r-port-num.txt") or "2650")


def read_home_file(name: str) -> str | None:
    path = Path.home() / name
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip() or None


def download_model(model_url: str, run_id: str) -> Path:
    parsed = urlparse(model_url)
    if parsed.scheme not in {"http", "https"}:
        raise ModelDownloadError("model_url must use http or https.")
    if not parsed.hostname:
        raise ModelDownloadError("model_url must include a hostname.")
    if not ALLOW_PRIVATE_URLS:
        reject_private_hostname(parsed.hostname)

    request = Request(model_url, headers={"User-Agent": "act-r-container/1.0"})
    try:
        with urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_MODEL_BYTES:
                raise ModelDownloadError(
                    f"Model is too large. Limit is {MAX_MODEL_BYTES} bytes."
                )

            data = response.read(MAX_MODEL_BYTES + 1)
            if len(data) > MAX_MODEL_BYTES:
                raise ModelDownloadError(
                    f"Model is too large. Limit is {MAX_MODEL_BYTES} bytes."
                )
    except HTTPError as exc:
        raise ModelDownloadError(f"Could not download model: HTTP {exc.code}.") from exc
    except URLError as exc:
        raise ModelDownloadError(f"Could not download model: {exc.reason}.") from exc

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / f"{run_id}.lisp"
    model_path.write_bytes(data)
    return model_path


def reject_private_hostname(hostname: str) -> None:
    try:
        addresses = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ModelDownloadError(f"Could not resolve model_url host {hostname!r}.") from exc

    for family, _, _, _, sockaddr in addresses:
        if family not in {socket.AF_INET, socket.AF_INET6}:
            continue
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ModelDownloadError(
                "model_url resolves to a private or local address. "
                "Set ACTR_ALLOW_PRIVATE_MODEL_URLS=true only for trusted development."
            )


class RequestHandler(BaseHTTPRequestHandler):
    runner = ActRRunner()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/health":
            self.write_json({"ok": True, "actr_host": default_actr_host(), "actr_port": default_actr_port()})
            return

        self.write_json(
            {
                "ok": True,
                "service": "ACT-R model runner",
                "endpoints": {
                    "POST /run-model": {
                        "body": {
                            "model_url": "https://example.com/model.lisp",
                            "run_seconds": DEFAULT_RUN_SECONDS,
                        }
                    },
                    "GET /health": "Health check",
                },
            }
        )

    def do_POST(self) -> None:
        if self.path != "/run-model":
            self.write_json({"ok": False, "error": "Not found."}, HTTPStatus.NOT_FOUND)
            return

        try:
            request = self.read_json_body()
            result = self.runner.run_model_url(request)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.UNPROCESSABLE_ENTITY
            self.write_json(result, status)
        except ValueError as exc:
            self.write_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except ModelDownloadError as exc:
            self.write_json({"ok": False, "phase": "download", "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - final API boundary
            self.write_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise ValueError("Request body must be JSON.")
        if content_length > 32 * 1024:
            raise ValueError("Request body is too large.")

        raw_body = self.rfile.read(content_length)
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON.") from exc
        if not isinstance(body, dict):
            raise ValueError("Request JSON must be an object.")
        return body

    def write_json(self, body: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", os.environ.get("ACTR_API_CORS_ORIGIN", "*"))
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt: str, *args: Any) -> None:
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


def main() -> int:
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), RequestHandler)
    print(f"ACT-R API server listening on port {port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
