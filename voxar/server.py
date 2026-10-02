"""Optional local HTTP/WebSocket server (extra: ``voxar[server]``). Thin: calls the facade.

Meant for a browser or phone app on the same machine. It has NO authentication, so it binds to
loopback by default and defends against the one attack a local server must expect from a web
page: DNS rebinding. Requests whose ``Host`` is not a loopback name, and WebSocket upgrades whose
``Origin`` is not a local page, are rejected. Upload size and stream length are capped.
"""

import asyncio
import contextlib
import json
import queue
import threading
from collections.abc import Callable, Iterator
from io import BytesIO
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

import voxar
from voxar.api import Voxar
from voxar.audio import read_wav_bytes, write_wav
from voxar.domain import (
    AudioChunk,
    EngineUnavailableError,
    InvalidAudioError,
    ModelNotFoundError,
    VoxarError,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

LOOPBACK_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})
ANY_HOST = "*"  # only used when the user explicitly exposes the server (--allow-remote)
_BYTES_PER_SECOND = 16_000 * 2
_STOP = object()


def _host_name(host_header: str) -> str:
    """The host part of a Host header value, without port or IPv6 brackets."""
    return (urlsplit("//" + host_header).hostname or "").lower()


def _host_allowed(host_header: str, allowed: frozenset[str]) -> bool:
    return ANY_HOST in allowed or _host_name(host_header) in allowed


def _origin_allowed(origin: str, allowed: frozenset[str]) -> bool:
    return ANY_HOST in allowed or (urlsplit(origin).hostname or "").lower() in allowed


def _status_for(error: Exception) -> int:
    if isinstance(error, (EngineUnavailableError, ModelNotFoundError)):
        return 503
    if isinstance(error, (InvalidAudioError, ValueError)):
        return 400
    return 500


class _Gate:
    """One job at a time, a few waiting, everyone else turned away.

    Measured on the development machine: running two inference jobs at once on one model was
    about 30% slower in total than running them one after another (a second model instance did
    not help either), and unbounded waiting turned load into multi-second latency and timeouts.
    So a gate admits one job, lets ``max_waiting`` more queue, and refuses the rest immediately
    so clients can back off.
    """

    def __init__(self, max_waiting: int) -> None:
        self.turn = threading.Lock()  # held while a job runs
        self._room = 1 + max_waiting
        self._pending = 0
        self._count = threading.Lock()

    def try_enter(self) -> bool:
        with self._count:
            if self._pending >= self._room:
                return False
            self._pending += 1
            return True

    def leave(self) -> None:
        with self._count:
            self._pending -= 1


def create_app(
    app: Voxar,
    engines: Callable[[], dict[str, list[str]]],
    *,
    allowed_hosts: frozenset[str] = LOOPBACK_NAMES,
    max_upload_bytes: int = 50 * 1024 * 1024,
    max_stream_seconds: float = 3600.0,
    max_streams: int = 4,
    max_waiting: int = 8,
) -> "FastAPI":
    from fastapi import FastAPI

    api = FastAPI(title="voxar", version=voxar.__version__, docs_url=None, redoc_url=None)
    _install_host_guard(api, allowed_hosts)
    _install_error_handlers(api)
    _install_http_routes(
        api,
        app,
        engines,
        allowed_hosts,
        max_upload_bytes=max_upload_bytes,
        max_waiting=max_waiting,
    )
    _install_ui_route(api)
    _install_stream_route(
        api, app, allowed_hosts, max_stream_seconds=max_stream_seconds, max_streams=max_streams
    )
    return api


def _install_host_guard(api: "FastAPI", allowed_hosts: frozenset[str]) -> None:
    from fastapi import Request, Response
    from fastapi.responses import JSONResponse

    @api.middleware("http")
    async def only_local_hosts(request: Request, call_next: Any) -> Response:
        if not _host_allowed(request.headers.get("host", ""), allowed_hosts):
            return JSONResponse({"error": "host not allowed"}, status_code=403)
        return await call_next(request)  # type: ignore[no-any-return]


def _install_error_handlers(api: "FastAPI") -> None:
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @api.exception_handler(VoxarError)
    async def voxar_error(_: Request, exc: VoxarError) -> JSONResponse:
        return JSONResponse({"error": str(exc)}, status_code=_status_for(exc))

    @api.exception_handler(ValueError)
    async def value_error(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse({"error": str(exc)}, status_code=400)


def _install_http_routes(
    api: "FastAPI",
    app: Voxar,
    engines: Callable[[], dict[str, list[str]]],
    allowed_hosts: frozenset[str],
    *,
    max_upload_bytes: int,
    max_waiting: int,
) -> None:
    from fastapi import Request, Response
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel

    class SpeakRequest(BaseModel):
        text: str
        voice: str | None = None

    asr_gate = _Gate(max_waiting)  # separate gates: speech-to-text and text-to-speech are
    tts_gate = _Gate(max_waiting)  # different engines, so they may overlap with each other

    def busy() -> JSONResponse:
        return JSONResponse(
            {"error": "server busy: too many requests waiting, try again shortly"},
            status_code=503,
            headers={"Retry-After": "1"},
        )

    @api.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": voxar.__version__, **engines()}

    @api.post("/v1/transcribe")
    async def transcribe(request: Request) -> JSONResponse:
        body = await _read_limited(request, max_upload_bytes)
        if body is None:
            return JSONResponse({"error": "upload too large"}, status_code=413)
        audio = read_wav_bytes(body)
        if not asr_gate.try_enter():
            return busy()

        def job() -> str:
            with asr_gate.turn:
                return app.transcribe_audio(audio)

        try:
            return JSONResponse({"text": await asyncio.to_thread(job)})
        finally:
            asr_gate.leave()

    @api.post("/v1/speak")
    async def speak(payload: SpeakRequest) -> Response:
        if not tts_gate.try_enter():
            return busy()

        def job() -> bytes:
            with tts_gate.turn:
                audio = app.speak(payload.text, voice=payload.voice)
            buffer = BytesIO()
            write_wav(buffer, audio)
            return buffer.getvalue()

        try:
            return Response(await asyncio.to_thread(job), media_type="audio/wav")
        finally:
            tts_gate.leave()


def _install_ui_route(api: "FastAPI") -> None:
    from importlib.resources import files

    from fastapi.responses import HTMLResponse

    page = files("voxar").joinpath("ui/index.html").read_text(encoding="utf-8")

    @api.get("/", include_in_schema=False)
    def index() -> HTMLResponse:
        return HTMLResponse(page)


def _install_stream_route(
    api: "FastAPI",
    app: Voxar,
    allowed_hosts: frozenset[str],
    *,
    max_stream_seconds: float,
    max_streams: int,
) -> None:
    from fastapi import WebSocket

    streams = threading.BoundedSemaphore(max_streams)  # concurrent live streams

    @api.websocket("/v1/stream")
    async def stream(ws: WebSocket) -> None:
        host_ok = _host_allowed(ws.headers.get("host", ""), allowed_hosts)
        origin = ws.headers.get("origin")
        if not host_ok or (origin is not None and not _origin_allowed(origin, allowed_hosts)):
            await ws.close(code=1008)
            return
        await ws.accept()
        if not streams.acquire(blocking=False):
            # Accept first: closing before the handshake completes reaches a real client as a
            # bare HTTP 403, indistinguishable from the Host/Origin rejection above.
            await ws.send_text(json.dumps({"error": "too many live streams, try again shortly"}))
            await ws.close(code=1013)  # "try again later"
            return
        try:
            await _Stream(ws, app, max_stream_seconds).run()
        finally:
            streams.release()


async def _read_limited(request: Any, limit: int) -> bytes | None:
    """The request body, or None if it exceeds ``limit`` bytes (checked while streaming)."""
    if int(request.headers.get("content-length") or 0) > limit:
        return None
    body = bytearray()
    async for block in request.stream():
        body += block
        if len(body) > limit:
            return None
    return bytes(body)


class _Stream:
    """One WebSocket session: PCM frames in, transcript events out.

    The recognizer is pull-based and blocking, so it runs in a worker thread that reads frames
    from a bounded queue; its events come back to the event loop through ``outgoing``.
    """

    def __init__(self, ws: Any, app: Voxar, max_seconds: float) -> None:
        self._ws = ws
        self._app = app
        self._max_seconds = max_seconds
        self._loop = asyncio.get_running_loop()
        self._incoming: queue.Queue[object] = queue.Queue(maxsize=200)
        self._outgoing: asyncio.Queue[object] = asyncio.Queue()
        self._received_seconds = 0.0

    async def run(self) -> None:
        worker = threading.Thread(target=self._recognize, daemon=True)
        worker.start()
        sender = asyncio.create_task(self._send_events())
        try:
            await self._receive_frames()
        except (VoxarError, ValueError) as exc:
            await self._ws.send_text(json.dumps({"error": str(exc)}))
        finally:
            self._incoming.put(_STOP)
            await asyncio.to_thread(worker.join)
            await sender
            with contextlib.suppress(RuntimeError):  # already closed by the client
                await self._ws.close()

    async def _receive_frames(self) -> None:
        while True:
            message = await self._ws.receive()
            if message.get("type") == "websocket.disconnect" or message.get("text") is not None:
                return  # a text frame ("end") finishes the stream
            data: bytes = message["bytes"]
            self._received_seconds += len(data) / _BYTES_PER_SECOND
            if self._received_seconds > self._max_seconds:
                raise ValueError(f"stream too long: limit is {self._max_seconds:g} s")
            self._incoming.put(AudioChunk(pcm=data))

    def _chunks(self) -> Iterator[AudioChunk]:
        while (item := self._incoming.get()) is not _STOP:
            yield item  # type: ignore[misc]

    def _recognize(self) -> None:
        try:
            for event in self._app.stream(self._chunks()):
                self._emit({"text": event.text, "final": event.is_final})
        except (VoxarError, ValueError) as exc:
            self._emit({"error": str(exc)})
        finally:
            self._emit(_STOP)

    def _emit(self, message: object) -> None:
        self._loop.call_soon_threadsafe(self._outgoing.put_nowait, message)

    async def _send_events(self) -> None:
        while (message := await self._outgoing.get()) is not _STOP:
            await self._ws.send_text(json.dumps(message, ensure_ascii=False))
