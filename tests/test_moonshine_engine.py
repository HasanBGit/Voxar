"""Adapter tests against a scripted fake of the moonshine_voice package (no model, no network)."""

import os
import sys
import threading
import types
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from voxar.config import Config
from voxar.domain import AudioChunk, EngineUnavailableError, ModelNotFoundError
from voxar.engines import moonshine as engine
from voxar.models import CATALOG, ModelStore
from voxar.testing import RecognizerContract


@dataclass
class _Line:
    text: str


class _Event:
    def __init__(self, text: str) -> None:
        self.line = _Line(text)


class _TextChanged(_Event):
    pass


class _Completed(_Event):
    pass


class _Started(_Event):
    pass


class FakeStream:
    """One per recognizer.stream() call: a text-changed event per chunk, completed on stop()."""

    def __init__(self) -> None:
        self.listeners: list[Callable[[Any], None]] = []
        self.audio: list[tuple[list[float], int]] = []
        self.started = self.stopped = self.closed = False

    def add_listener(self, listener: Callable[[Any], None]) -> None:
        self.listeners.append(listener)

    def start(self) -> None:
        self.started = True

    def add_audio(self, samples: list[float], rate: int) -> None:
        self.audio.append((samples, rate))
        for listener in self.listeners:
            listener(_Started(""))  # must be ignored
            listener(_TextChanged(f"partial{len(self.audio)}"))

    def stop(self) -> None:
        self.stopped = True
        if self.audio:
            for listener in self.listeners:
                listener(_Completed("final text"))

    def close(self) -> None:
        self.closed = True


class FakeTranscriber:
    """The loaded model. Constructing it is the expensive step the adapter must do only once."""

    instances: list["FakeTranscriber"] = []

    def __init__(self, model_path: Any, model_arch: Any) -> None:
        self.model_path = model_path
        self.model_arch = model_arch
        self.streams: list[FakeStream] = []
        self.closed = False
        FakeTranscriber.instances.append(self)

    def create_stream(self) -> FakeStream:
        stream = FakeStream()
        self.streams.append(stream)
        return stream

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def fake_moonshine(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    FakeTranscriber.instances.clear()
    api = types.ModuleType("moonshine_voice.moonshine_api")
    api.ModelArch = lambda value: f"arch{value}"  # type: ignore[attr-defined]
    transcriber = types.ModuleType("moonshine_voice.transcriber")
    transcriber.Transcriber = FakeTranscriber  # type: ignore[attr-defined]
    transcriber.LineTextChanged = _TextChanged  # type: ignore[attr-defined]
    transcriber.LineCompleted = _Completed  # type: ignore[attr-defined]
    package = types.ModuleType("moonshine_voice")
    monkeypatch.setitem(sys.modules, "moonshine_voice", package)
    monkeypatch.setitem(sys.modules, "moonshine_voice.moonshine_api", api)
    monkeypatch.setitem(sys.modules, "moonshine_voice.transcriber", transcriber)
    yield


def recognizer() -> engine.MoonshineRecognizer:
    return engine.MoonshineRecognizer(model_dir=Path("/models/x"), arch=2)


def pcm(*samples: int) -> bytes:
    return b"".join(s.to_bytes(2, "little", signed=True) for s in samples)


class TestMoonshineContract(RecognizerContract):
    make_recognizer = staticmethod(recognizer)


def test_partials_then_final_and_started_events_are_ignored() -> None:
    events = list(recognizer().stream([AudioChunk(pcm=pcm(0, 0)), AudioChunk(pcm=pcm(0, 0))]))
    assert [(e.text, e.is_final) for e in events] == [
        ("partial1", False),
        ("partial2", False),
        ("final text", True),
    ]


def test_pcm16_is_converted_to_floats_in_range() -> None:
    list(recognizer().stream([AudioChunk(pcm=pcm(0, 16384, -32768, 32767))]))
    samples, rate = FakeTranscriber.instances[0].streams[0].audio[0]
    assert rate == 16_000
    assert samples[:3] == [0.0, 0.5, -1.0]
    assert samples[3] == pytest.approx(32767 / 32768)


def test_model_path_and_arch_are_passed_through() -> None:
    list(recognizer().stream([AudioChunk(pcm=pcm(0))]))
    fake = FakeTranscriber.instances[0]
    assert fake.model_path == Path("/models/x")
    assert fake.model_arch == "arch2"
    stream = fake.streams[0]
    assert stream.started and stream.stopped and stream.closed


def test_the_stream_is_closed_when_the_consumer_stops_early() -> None:
    events = recognizer().stream([AudioChunk(pcm=pcm(0))] * 5)
    next(events)
    events.close()
    assert FakeTranscriber.instances[0].streams[0].closed


def test_the_model_is_loaded_once_and_shared_by_every_stream() -> None:
    rec = recognizer()
    for _ in range(3):
        list(rec.stream([AudioChunk(pcm=pcm(0))]))
    assert len(FakeTranscriber.instances) == 1
    assert len(FakeTranscriber.instances[0].streams) == 3
    assert all(stream.closed for stream in FakeTranscriber.instances[0].streams)


def test_concurrent_streams_share_one_model_and_stay_independent() -> None:
    rec = recognizer()
    results: list[list[str]] = []

    def work() -> None:
        results.append([e.text for e in rec.stream([AudioChunk(pcm=pcm(0))] * 2)])

    threads = [threading.Thread(target=work) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(FakeTranscriber.instances) == 1  # no race created a second model
    assert len(results) == 6
    assert all(texts == ["partial1", "partial2", "final text"] for texts in results)


def test_close_releases_the_model_and_a_later_stream_reloads_it() -> None:
    rec = recognizer()
    list(rec.stream([AudioChunk(pcm=pcm(0))]))
    rec.close()
    assert FakeTranscriber.instances[0].closed
    list(rec.stream([AudioChunk(pcm=pcm(0))]))
    assert len(FakeTranscriber.instances) == 2


def test_empty_stream_creates_no_events() -> None:
    assert list(recognizer().stream([])) == []


def test_missing_optional_dependency_gives_install_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "moonshine_voice", None)
    monkeypatch.setitem(sys.modules, "moonshine_voice.transcriber", None)
    with pytest.raises(EngineUnavailableError, match=r"voxar\[moonshine\]"):
        list(recognizer().stream([AudioChunk(pcm=pcm(0))]))


def test_create_requires_the_model_to_be_installed(tmp_path: Path) -> None:
    with pytest.raises(ModelNotFoundError, match="voxar models pull"):
        engine.create(Config(cache_dir=tmp_path))


def test_create_verifies_installed_files_and_returns_a_recognizer(tmp_path: Path) -> None:
    spec = CATALOG[engine.MODEL_ID]
    target = ModelStore(tmp_path).path(spec)
    target.mkdir(parents=True)
    for model_file in spec.files:
        (target / model_file.name).write_bytes(b"tampered")
    from voxar.domain import ModelIntegrityError

    with pytest.raises(ModelIntegrityError):
        engine.create(Config(cache_dir=tmp_path))


class NoisyTranscriber(FakeTranscriber):
    """Like the real one: its native code prints straight to file descriptor 2 while loading."""

    fail = False

    def __init__(self, model_path: Any, model_arch: Any) -> None:
        os.write(2, b"native tokenizer warning\n")
        if NoisyTranscriber.fail:
            raise RuntimeError("model could not be opened")
        super().__init__(model_path, model_arch)


def use_noisy_transcriber(monkeypatch: pytest.MonkeyPatch, *, fail: bool) -> None:
    NoisyTranscriber.fail = fail
    monkeypatch.setattr(sys.modules["moonshine_voice.transcriber"], "Transcriber", NoisyTranscriber)


def test_native_diagnostics_during_a_successful_load_are_not_shown(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    use_noisy_transcriber(monkeypatch, fail=False)
    list(recognizer().stream([AudioChunk(pcm=pcm(0))]))
    assert capfd.readouterr().err == ""


def test_native_diagnostics_are_shown_when_the_load_fails(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    use_noisy_transcriber(monkeypatch, fail=True)
    with pytest.raises(RuntimeError, match="could not be opened"):
        list(recognizer().stream([AudioChunk(pcm=pcm(0))]))
    assert "native tokenizer warning" in capfd.readouterr().err


def test_stderr_works_normally_after_a_load(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    use_noisy_transcriber(monkeypatch, fail=False)
    list(recognizer().stream([AudioChunk(pcm=pcm(0))]))
    os.write(2, b"later message\n")
    assert capfd.readouterr().err == "later message\n"


def test_warm_loads_the_model_once_before_any_audio() -> None:
    rec = recognizer()
    rec.warm()
    assert len(FakeTranscriber.instances) == 1
    list(rec.stream([AudioChunk(pcm=pcm(0))]))
    assert len(FakeTranscriber.instances) == 1  # the stream reused the warmed model
