"""Voice capture is pure logic over chunks: test it with synthetic loud and quiet blocks."""

import struct
from collections.abc import Iterator

import pytest

from voxar.domain import AudioChunk, EngineUnavailableError, SynthesizedAudio
from voxar.voice import level, play_audio, record_utterance

BLOCK = 1600  # 100 ms at 16 kHz


def loud(amplitude: int = 3000) -> AudioChunk:
    return AudioChunk(pcm=struct.pack("<h", amplitude) * BLOCK)


def quiet() -> AudioChunk:
    return AudioChunk(pcm=bytes(2 * BLOCK))


def test_level_is_zero_for_silence_and_the_amplitude_for_a_constant_tone() -> None:
    assert level(bytes(200)) == 0.0
    assert level(b"") == 0.0
    assert level(struct.pack("<h", -2000) * 50) == pytest.approx(2000)


def test_a_phrase_ends_after_the_silence_and_includes_it() -> None:
    chunks = [quiet(), loud(), loud(), quiet(), quiet(), quiet(), loud()]  # last is never read
    audio = record_utterance(iter(chunks), max_seconds=10, silence_seconds=0.3)
    assert audio is not None
    # 1 pre-roll block + 2 loud + 3 quiet blocks; the stray loud block after the pause is ignored
    assert len(audio.pcm) == 6 * BLOCK * 2


def test_pre_roll_is_limited_to_three_blocks() -> None:
    chunks = [quiet()] * 10 + [loud(), quiet(), quiet()]
    audio = record_utterance(iter(chunks), max_seconds=10, silence_seconds=0.2)
    assert audio is not None
    assert len(audio.pcm) == (3 + 1 + 2) * BLOCK * 2


def test_nobody_speaking_returns_none_after_the_wait() -> None:
    read = []

    def source() -> Iterator[AudioChunk]:
        for _ in range(1000):
            read.append(1)
            yield quiet()

    assert record_utterance(source(), max_seconds=30, silence_seconds=1, wait_seconds=1.0) is None
    assert len(read) == 10  # stopped after 1.0 s of silence, not after 1000 blocks


def test_a_long_phrase_is_cut_off_at_max_seconds() -> None:
    audio = record_utterance(iter([loud()] * 100), max_seconds=2.0, silence_seconds=1.5)
    assert audio is not None
    assert audio.duration_s == pytest.approx(2.0)


def test_the_source_is_closed_so_the_microphone_is_released() -> None:
    closed = []

    def source() -> Iterator[AudioChunk]:
        try:
            while True:
                yield loud()
        finally:
            closed.append(True)

    record_utterance(source(), max_seconds=1.0, silence_seconds=1.0)
    assert closed == [True]


def test_wait_cannot_exceed_max_seconds() -> None:
    chunks = iter([quiet()] * 50)
    assert record_utterance(chunks, max_seconds=1.0, silence_seconds=1.0, wait_seconds=8.0) is None
    assert len(list(chunks)) == 40  # 10 blocks consumed, not 50


def test_playing_audio_without_the_audio_library_gives_an_install_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    monkeypatch.setitem(sys.modules, "sounddevice", None)
    with pytest.raises(EngineUnavailableError, match="voxar\\[moonshine\\]"):
        play_audio(SynthesizedAudio(pcm=bytes(100), sample_rate=24_000))
