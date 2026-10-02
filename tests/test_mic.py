import sys
import types
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from voxar.domain import EngineUnavailableError, InvalidAudioError
from voxar.mic import mic_chunks


class FakeInputStream:
    """Stands in for sounddevice.RawInputStream: feeds scripted blocks, then stops."""

    blocks: list[bytes] = []
    kwargs: dict[str, Any] = {}

    def __init__(self, *, callback: Callable[..., None], **kwargs: Any) -> None:
        self.callback = callback
        FakeInputStream.kwargs = kwargs

    def __enter__(self) -> "FakeInputStream":
        for block in FakeInputStream.blocks:
            self.callback(block, len(block) // 2, None, None)
        return self

    def __exit__(self, *_: object) -> None:
        return None


@pytest.fixture
def fake_sounddevice(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    module = types.ModuleType("sounddevice")
    module.RawInputStream = FakeInputStream  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sounddevice", module)
    yield


def test_reads_16k_mono_int16_blocks(fake_sounddevice: None) -> None:
    FakeInputStream.blocks = [bytes(3200), bytes(3200)]
    chunks = mic_chunks(block_ms=100, max_blocks=2)
    first = next(chunks)
    assert (first.sample_rate, first.channels, len(first.pcm)) == (16_000, 1, 3200)
    assert len(list(chunks)) == 1
    assert FakeInputStream.kwargs["samplerate"] == 16_000
    assert FakeInputStream.kwargs["channels"] == 1
    assert FakeInputStream.kwargs["dtype"] == "int16"
    assert FakeInputStream.kwargs["blocksize"] == 1600


def test_missing_sounddevice_gives_install_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "sounddevice", None)
    with pytest.raises(EngineUnavailableError, match=r"voxar\[moonshine\]|sounddevice"):
        next(mic_chunks())


def test_silent_device_fails_fast_with_a_hint(fake_sounddevice: None) -> None:
    FakeInputStream.blocks = []
    with pytest.raises(InvalidAudioError, match="microphone"):
        next(mic_chunks(timeout_s=0.01))


def test_ctrl_c_ends_the_stream_cleanly(
    fake_sounddevice: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    class InterruptedQueue:
        def __init__(self, maxsize: int = 0) -> None:
            pass

        def put_nowait(self, item: bytes) -> None:
            pass

        def get(self, timeout: float) -> bytes:
            raise KeyboardInterrupt

    monkeypatch.setattr("voxar.mic.queue.Queue", InterruptedQueue)
    assert list(mic_chunks()) == []
