"""Moonshine streaming speech recognizer (optional dependency: ``voxar[moonshine]``).

Moonshine delivers events synchronously while audio is added, so this adapter simply collects
them after each chunk and yields them. ``moonshine_voice`` is imported only when a stream starts.
"""

import contextlib
import os
import sys
import tempfile
import threading
from array import array
from collections.abc import Generator, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from voxar.config import Config
from voxar.domain import AudioChunk, EngineUnavailableError, TranscriptEvent
from voxar.models import CATALOG, ModelStore

MODEL_ID = "moonshine-tiny-streaming-ar"
MODEL_ARCH = 2  # moonshine_voice.ModelArch.TINY_STREAMING


@dataclass(frozen=True)
class _Api:
    """The few moonshine_voice names we use, loaded lazily."""

    transcriber: Any
    model_arch: Any
    text_changed: Any
    completed: Any


def _load_api() -> _Api:
    try:
        from moonshine_voice.moonshine_api import ModelArch
        from moonshine_voice.transcriber import LineCompleted, LineTextChanged, Transcriber
    except ImportError as exc:
        raise EngineUnavailableError(
            "the moonshine engine needs an optional dependency: pip install 'voxar[moonshine]'"
        ) from exc
    return _Api(Transcriber, ModelArch, LineTextChanged, LineCompleted)


@contextlib.contextmanager
def _held_back_native_stderr() -> Iterator[None]:
    """Moonshine's C++ code prints diagnostics straight to file descriptor 2 while it loads (for
    example a harmless tokenizer notice on every start). Hold them back; show them only if the
    load fails, so a real error is never hidden. Output other threads write to stderr during the
    load (well under a second, once per process) is held back with it."""
    sys.stderr.flush()
    saved = os.dup(2)
    with tempfile.TemporaryFile() as sink:
        os.dup2(sink.fileno(), 2)
        try:
            yield
        except BaseException:
            os.dup2(saved, 2)
            sink.seek(0)
            sys.stderr.write(sink.read().decode(errors="replace"))
            sys.stderr.flush()
            raise
        finally:
            os.dup2(saved, 2)
            os.close(saved)


def _to_floats(pcm: bytes) -> list[float]:
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder == "big":
        samples.byteswap()
    return [s / 32768.0 for s in samples]


def _drain(pending: list[Any], api: _Api) -> Iterator[TranscriptEvent]:
    events, pending[:] = list(pending), []
    for event in events:
        text = event.line.text
        if not text.strip():
            continue
        if isinstance(event, api.completed):
            yield TranscriptEvent(text=text, is_final=True)
        elif isinstance(event, api.text_changed):
            yield TranscriptEvent(text=text, is_final=False)


class MoonshineRecognizer:
    """Loads the model once (on first use) and gives each ``stream()`` call its own stream.

    Moonshine documents that all API calls are thread-safe and that work on one transcriber is
    serialized, so many threads can share the loaded model: a server pays the load cost once.
    """

    def __init__(self, model_dir: Path, arch: int) -> None:
        self._model_dir = model_dir
        self._arch = arch
        self._lock = threading.Lock()
        self._shared: tuple[_Api, Any] | None = None

    def _transcriber(self) -> tuple[_Api, Any]:
        with self._lock:
            if self._shared is None:
                api = _load_api()
                with _held_back_native_stderr():
                    model = api.transcriber(
                        model_path=self._model_dir, model_arch=api.model_arch(self._arch)
                    )
                self._shared = (api, model)
            return self._shared

    def warm(self) -> None:
        """Load the model now instead of on the first stream."""
        self._transcriber()

    def close(self) -> None:
        """Release the loaded model. A later ``stream()`` call loads it again."""
        with self._lock:
            if self._shared is not None:
                self._shared[1].close()
                self._shared = None

    def stream(self, chunks: Iterable[AudioChunk]) -> Generator[TranscriptEvent, None, None]:
        api, model = self._transcriber()
        session = model.create_stream()
        pending: list[Any] = []
        session.add_listener(pending.append)
        session.start()
        try:
            for chunk in chunks:
                session.add_audio(_to_floats(chunk.pcm), chunk.sample_rate)
                yield from _drain(pending, api)
            session.stop()
            yield from _drain(pending, api)
        finally:
            session.close()


def create(config: Config) -> MoonshineRecognizer:
    """Entry-point factory: verifies the installed model before returning a recognizer."""
    spec = CATALOG[MODEL_ID]
    store = ModelStore(config.cache_dir, offline=config.offline)
    store.verify(spec)
    return MoonshineRecognizer(model_dir=store.path(spec), arch=MODEL_ARCH)
