"""A tiny local HTTP server that imitates LLM provider APIs, so tests need no network and no key."""

import json
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

Reply = tuple[int, dict[str, str], bytes]  # status, headers, body


class FakeLLMServer:
    """Records every request; ``responder(path, body, headers)`` decides the answer."""

    def __init__(self, responder: Callable[[str, dict[str, Any], dict[str, str]], Reply]) -> None:
        self.requests: list[dict[str, Any]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:  # silence the test output
                return

            def _handle(self) -> None:
                length = int(self.headers.get("content-length") or 0)
                raw = self.rfile.read(length) if length else b""
                body = json.loads(raw) if raw else {}
                headers = {k.lower(): v for k, v in self.headers.items()}
                outer.requests.append({"method": self.command, "path": self.path, "body": body, "headers": headers})
                status, extra, payload = responder(self.path, body, headers)
                self.send_response(status)
                for key, value in extra.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST = _handle  # noqa: N815

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self._server.server_address[1]}/v1"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "FakeLLMServer":
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._server.shutdown()
        self._server.server_close()


def json_reply(payload: dict[str, Any], status: int = 200, **headers: str) -> Reply:
    return status, {"Content-Type": "application/json", **headers}, json.dumps(payload).encode()


def sse_reply(events: Iterator[str]) -> Reply:
    return 200, {"Content-Type": "text/event-stream"}, "".join(events).encode()


def openai_message(content: str | None, **extra: Any) -> dict[str, Any]:
    return {"choices": [{"message": {"role": "assistant", "content": content, **extra}, "finish_reason": "stop"}]}


def openai_stream(pieces: list[str]) -> Iterator[str]:
    for piece in pieces:
        yield "data: " + json.dumps({"choices": [{"delta": {"content": piece}}]}) + "\n\n"
    yield "data: [DONE]\n\n"


def anthropic_stream(pieces: list[str]) -> Iterator[str]:
    yield 'event: message_start\ndata: {"type":"message_start"}\n\n'
    for piece in pieces:
        data = {"type": "content_block_delta", "delta": {"type": "text_delta", "text": piece}}
        yield "event: content_block_delta\ndata: " + json.dumps(data) + "\n\n"
    yield 'event: message_stop\ndata: {"type":"message_stop"}\n\n'
