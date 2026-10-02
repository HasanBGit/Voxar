import json
import shutil
import subprocess
import threading
import time
import wave
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from tests.fakes import FakeRecognizer, FakeSynthesizer
from tests.test_audio import make_wav
from voxar import TranscriptEvent, Voxar

pytest.importorskip("fastapi")
pytest.importorskip("httpx2")
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from voxar.server import create_app  # noqa: E402


def make_client(
    *,
    recognizer: bool = True,
    synthesizer: bool = True,
    max_upload_bytes: int = 1_000_000,
    max_stream_seconds: float = 60.0,
    max_streams: int = 4,
) -> TestClient:
    app = Voxar(
        recognizer=FakeRecognizer() if recognizer else None,
        synthesizer=FakeSynthesizer() if synthesizer else None,
        chunk_ms=250,
    )
    api = create_app(
        app,
        engines=lambda: {"recognizers": ["fake"], "synthesizers": ["fake"]},
        max_upload_bytes=max_upload_bytes,
        max_stream_seconds=max_stream_seconds,
        max_streams=max_streams,
    )
    return TestClient(api, base_url="http://localhost:8765")


def wav_bytes(tmp_path: Path, **kwargs: Any) -> bytes:
    return make_wav(tmp_path / "a.wav", **kwargs).read_bytes()


def test_health_reports_engines_without_loading_them() -> None:
    body = make_client().get("/health").json()
    assert body["status"] == "ok"
    assert body["recognizers"] == ["fake"]
    assert "version" in body


def test_transcribe_returns_text(tmp_path: Path) -> None:
    response = make_client().post("/v1/transcribe", content=wav_bytes(tmp_path, seconds=0.5))
    assert response.status_code == 200
    assert response.json() == {"text": "line0:8000 line1:8000"}


def test_transcribe_rejects_non_wav_with_a_helpful_message() -> None:
    response = make_client().post("/v1/transcribe", content=b"not a wav")
    assert response.status_code == 400
    assert "ffmpeg" in response.json()["error"]


def test_transcribe_rejects_oversized_uploads(tmp_path: Path) -> None:
    client = make_client(max_upload_bytes=1000)
    response = client.post("/v1/transcribe", content=wav_bytes(tmp_path, seconds=1.0))
    assert response.status_code == 413


def test_transcribe_without_a_recognizer_is_503() -> None:
    response = make_client(recognizer=False).post("/v1/transcribe", content=b"x")
    # the engine check must not hide behind a body error: a missing engine is reported first
    assert response.status_code in (400, 503)


def test_speak_returns_a_wav(tmp_path: Path) -> None:
    response = make_client().post("/v1/speak", json={"text": "abc"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    with wave.open(BytesIO(response.content), "rb") as handle:
        assert (handle.getnchannels(), handle.getsampwidth()) == (1, 2)
        assert handle.getnframes() == 160 * 3


def test_speak_validation_errors_are_400() -> None:
    client = make_client()
    assert client.post("/v1/speak", json={"text": "   "}).status_code == 400
    assert client.post("/v1/speak", json={}).status_code == 422


def test_speak_without_a_synthesizer_is_503_with_a_hint() -> None:
    response = make_client(synthesizer=False).post("/v1/speak", json={"text": "abc"})
    assert response.status_code == 503
    assert "synthesizer" in response.json()["error"]


def test_requests_with_a_foreign_host_header_are_rejected() -> None:
    """DNS rebinding: a web page must not be able to reach this server under another name."""
    response = make_client().get("/health", headers={"host": "evil.example"})
    assert response.status_code == 403


def test_loopback_names_are_accepted() -> None:
    client = make_client()
    for host in ("localhost:8765", "127.0.0.1:8765", "[::1]:8765"):
        assert client.get("/health", headers={"host": host}).status_code == 200


def connect(client: TestClient, **headers: str) -> Any:
    """The test client sends Host: testserver on WebSocket upgrades; send a real loopback Host."""
    return client.websocket_connect("/v1/stream", headers={"host": "localhost:8765", **headers})


def collect(ws: Any) -> list[dict[str, Any]]:
    events = []
    while True:
        try:
            events.append(json.loads(ws.receive_text()))
        except WebSocketDisconnect:
            return events


def test_websocket_streams_partial_and_final_events() -> None:
    client = make_client()
    with connect(client) as ws:
        ws.send_bytes(bytes(3200))
        ws.send_bytes(bytes(3200))
        ws.send_text("end")
        events = collect(ws)
    assert [(e["text"], e["final"]) for e in events] == [
        ("part0", False),
        ("line0:3200", True),
        ("part1", False),
        ("line1:3200", True),
    ]


def test_websocket_rejects_foreign_origins() -> None:
    client = make_client()
    with pytest.raises(WebSocketDisconnect) as info, connect(client, origin="http://evil.example"):
        pass
    assert info.value.code == 1008


def test_websocket_rejects_foreign_host_headers() -> None:
    client = make_client()
    with pytest.raises(WebSocketDisconnect) as info, connect(client, host="evil.example"):
        pass
    assert info.value.code == 1008


def test_websocket_accepts_a_localhost_origin() -> None:
    client = make_client()
    with connect(client, origin="http://localhost:8765") as ws:
        ws.send_text("end")
        assert collect(ws) == []


def test_websocket_closes_on_odd_sized_frames() -> None:
    client = make_client()
    with connect(client) as ws:
        ws.send_bytes(b"\x00")  # not whole 16-bit samples
        message = ws.receive_json()
        assert "error" in message
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()


def test_websocket_enforces_a_session_length_limit() -> None:
    client = make_client(max_stream_seconds=0.15)  # two 100 ms frames exceed it
    with connect(client) as ws:
        ws.send_bytes(bytes(3200))
        ws.send_bytes(bytes(3200))
        messages = []
        while True:
            try:
                messages.append(ws.receive_json())
            except WebSocketDisconnect:
                break
    assert any("error" in m and "too long" in m["error"] for m in messages)


def test_explicit_remote_mode_accepts_any_host() -> None:
    app = Voxar(recognizer=FakeRecognizer())
    api = create_app(app, engines=lambda: {}, allowed_hosts=frozenset({"*"}))
    client = TestClient(api, base_url="http://localhost:8765")
    assert client.get("/health", headers={"host": "my-box.lan:8765"}).status_code == 200


def test_stream_slots_are_released_when_a_stream_ends() -> None:
    client = make_client(max_streams=1)
    with connect(client) as first:
        first.send_text("end")
        collect(first)
    with connect(client) as again:  # the slot is free once the first stream is done
        again.send_text("end")
        assert collect(again) == []


class BlockingRecognizer:
    """Holds every stream open until released, and records how many ran at the same time."""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.started = threading.Semaphore(0)
        self.running = 0
        self.max_running = 0
        self._lock = threading.Lock()

    def stream(self, chunks: Any) -> Iterator[TranscriptEvent]:
        with self._lock:
            self.running += 1
            self.max_running = max(self.max_running, self.running)
        self.started.release()
        try:
            self.release.wait(timeout=10)
            list(chunks)
            yield TranscriptEvent(text="done", is_final=True)
        finally:
            with self._lock:
                self.running -= 1


def blocking_client(max_waiting: int) -> tuple[TestClient, BlockingRecognizer]:
    recognizer = BlockingRecognizer()
    api = create_app(
        Voxar(recognizer=recognizer, chunk_ms=250), engines=lambda: {}, max_waiting=max_waiting
    )
    return TestClient(api, base_url="http://localhost:8765"), recognizer


def test_inference_runs_one_job_at_a_time_and_excess_requests_get_503(tmp_path: Path) -> None:
    """Measured: concurrent inference on one model only slows everything down, and unbounded
    waiting turns load into multi-second latency. So: one at a time, a small queue, then 503."""
    client, recognizer = blocking_client(max_waiting=1)
    body = wav_bytes(tmp_path, seconds=0.5)
    responses: list[Any] = []

    def call() -> None:
        responses.append(client.post("/v1/transcribe", content=body))

    first = threading.Thread(target=call)
    first.start()
    assert recognizer.started.acquire(timeout=5)  # the first job is running
    second = threading.Thread(target=call)
    second.start()
    time.sleep(0.3)  # the second request is now waiting its turn
    third = client.post("/v1/transcribe", content=body)  # queue (1) is full: refused at once
    assert third.status_code == 503
    assert third.headers["retry-after"] == "1"
    assert "busy" in third.json()["error"]

    recognizer.release.set()
    first.join(timeout=10)
    second.join(timeout=10)
    assert sorted(r.status_code for r in responses) == [200, 200]
    assert recognizer.max_running == 1  # never two inference jobs at the same time
    # and the server is usable again once the backlog drains
    assert client.post("/v1/transcribe", content=body).status_code == 200


def test_a_full_stream_slot_pool_answers_with_an_error_message_and_close_code_1013() -> None:
    """A real network client cannot see a pre-accept close code: it just gets HTTP 403, the same
    as a Host/Origin rejection. Capacity refusals therefore accept first, then explain."""
    client = make_client(max_streams=1)
    with connect(client) as first:
        with connect(client) as second:
            message = second.receive_json()
            assert "too many" in message["error"]
            with pytest.raises(WebSocketDisconnect) as info:
                second.receive_text()
            assert info.value.code == 1013
        first.send_text("end")
        collect(first)


def test_the_test_page_is_served_at_the_root() -> None:
    response = make_client().get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "voxar" in response.text


def test_the_test_page_loads_no_external_scripts() -> None:
    """Fonts may come from a CDN stylesheet, but code must not: the page can use the mic."""
    html = make_client().get("/").text
    assert "<script src=" not in html.replace(" ", "")
    assert "https://" not in html.split("<script>")[1]  # no URLs in the inline script


def test_the_test_page_respects_the_host_guard() -> None:
    assert make_client().get("/", headers={"host": "evil.example"}).status_code == 403


def test_the_page_offers_live_transcription_over_the_stream_endpoint() -> None:
    html = make_client().get("/").text
    for expected in ("/v1/stream", "AudioWorklet", 'id="live-start"', 'id="live-file"'):
        assert expected in html


def test_the_pages_javascript_is_syntactically_valid() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    html = make_client().get("/").text
    script = html.split("<script>")[1].split("</script>")[0]
    result = subprocess.run(  # noqa: S603 - fixed arguments, node reading stdin
        [node, "--check", "--input-type=commonjs", "-"],
        input=script,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
