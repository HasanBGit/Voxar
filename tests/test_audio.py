import wave
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from voxar.audio import chunked, read_wav, read_wav_bytes, write_wav
from voxar.domain import AudioChunk, InvalidAudioError, SynthesizedAudio


def make_wav(
    path: Path,
    *,
    seconds: float = 1.0,
    rate: int = 16_000,
    channels: int = 1,
    width: int = 2,
) -> Path:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(width)
        handle.setframerate(rate)
        handle.writeframes(bytes(int(seconds * rate) * channels * width))
    return path


def test_read_wav_returns_16k_mono_chunk(tmp_path: Path) -> None:
    chunk = read_wav(make_wav(tmp_path / "a.wav", seconds=0.5))
    assert (chunk.sample_rate, chunk.channels) == (16_000, 1)
    assert chunk.duration_s == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("kwargs", "hint"),
    [
        ({"rate": 8_000}, "16000"),
        ({"channels": 2}, "mono"),
        ({"width": 1}, "16-bit"),
    ],
)
def test_read_wav_rejects_unsupported_format_with_fix_hint(
    tmp_path: Path, kwargs: dict[str, int], hint: str
) -> None:
    with pytest.raises(InvalidAudioError, match=hint):
        read_wav(make_wav(tmp_path / "a.wav", **kwargs))


def test_read_wav_missing_file(tmp_path: Path) -> None:
    with pytest.raises(InvalidAudioError, match="not found"):
        read_wav(tmp_path / "nope.wav")


def test_read_wav_not_a_wav(tmp_path: Path) -> None:
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"this is not audio")
    with pytest.raises(InvalidAudioError, match="valid WAV"):
        read_wav(bad)


def test_read_wav_enforces_max_duration(tmp_path: Path) -> None:
    path = make_wav(tmp_path / "long.wav", seconds=2.0)
    with pytest.raises(InvalidAudioError, match="longer than"):
        read_wav(path, max_seconds=1.0)


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    audio = SynthesizedAudio(pcm=bytes(range(256)) * 2, sample_rate=16_000)
    out = tmp_path / "out.wav"
    write_wav(out, audio)
    assert read_wav(out).pcm == audio.pcm


def test_chunked_rejects_non_positive_size() -> None:
    with pytest.raises(ValueError, match="chunk_ms"):
        list(chunked(AudioChunk(pcm=b""), chunk_ms=0))


@given(
    frames=st.integers(min_value=0, max_value=5_000),
    chunk_ms=st.integers(min_value=1, max_value=500),
)
def test_chunked_preserves_audio_and_respects_size(frames: int, chunk_ms: int) -> None:
    audio = AudioChunk(pcm=bytes(i % 251 for i in range(frames * 2)))
    parts = list(chunked(audio, chunk_ms=chunk_ms))
    assert b"".join(p.pcm for p in parts) == audio.pcm
    limit = 16_000 * chunk_ms // 1000 * 2
    assert all(len(p.pcm) <= max(limit, 2) for p in parts)
    assert all(len(p.pcm) % 2 == 0 for p in parts)


def test_read_wav_bytes_matches_read_wav(tmp_path: Path) -> None:
    path = make_wav(tmp_path / "a.wav", seconds=0.25)
    assert read_wav_bytes(path.read_bytes()) == read_wav(path)


def test_read_wav_bytes_rejects_garbage_and_wrong_format() -> None:
    with pytest.raises(InvalidAudioError, match="valid WAV"):
        read_wav_bytes(b"not audio at all")


def test_read_wav_bytes_rejects_stereo(tmp_path: Path) -> None:
    stereo = make_wav(tmp_path / "s.wav", channels=2).read_bytes()
    with pytest.raises(InvalidAudioError, match="mono"):
        read_wav_bytes(stereo)


def test_read_wav_bytes_enforces_max_duration(tmp_path: Path) -> None:
    data = make_wav(tmp_path / "l.wav", seconds=2.0).read_bytes()
    with pytest.raises(InvalidAudioError, match="longer than"):
        read_wav_bytes(data, max_seconds=1.0)
