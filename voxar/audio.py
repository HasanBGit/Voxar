"""WAV reading/writing and chunking, using only the standard library.

Only 16 kHz mono 16-bit PCM WAV is accepted. Anything else fails fast with the command that
converts it, rather than guessing or silently resampling.
"""

import io
import wave
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

from voxar.domain import AudioChunk, InvalidAudioError, SynthesizedAudio

TARGET_RATE = 16_000
_BYTES_PER_SAMPLE = 2
_CONVERT_HINT = "convert with: ffmpeg -i INPUT -ar 16000 -ac 1 -sample_fmt s16 OUTPUT.wav"


def read_wav(path: str | Path, *, max_seconds: float = 3600.0) -> AudioChunk:
    """Read a 16 kHz mono 16-bit PCM WAV file."""
    source = Path(path)
    try:
        with source.open("rb") as handle:
            return _decode(handle, str(source), max_seconds)
    except FileNotFoundError:
        raise InvalidAudioError(f"audio file not found: {source}") from None


def read_wav_bytes(data: bytes, *, max_seconds: float = 3600.0) -> AudioChunk:
    """Decode 16 kHz mono 16-bit PCM WAV data held in memory."""
    return _decode(io.BytesIO(data), "uploaded audio", max_seconds)


def _decode(stream: BinaryIO, label: str, max_seconds: float) -> AudioChunk:
    try:
        with wave.open(stream, "rb") as handle:
            _check_format(handle.getsampwidth(), handle.getnchannels(), handle.getframerate())
            if handle.getnframes() / handle.getframerate() > max_seconds:
                raise InvalidAudioError(f"audio is longer than {max_seconds:g} s: {label}")
            pcm = handle.readframes(handle.getnframes())
    except (wave.Error, EOFError):
        raise InvalidAudioError(f"not a valid WAV file: {label}; {_CONVERT_HINT}") from None
    return AudioChunk(pcm=pcm, sample_rate=TARGET_RATE, channels=1)


def _check_format(width: int, channels: int, rate: int) -> None:
    if width != _BYTES_PER_SAMPLE:
        raise InvalidAudioError(
            f"only 16-bit PCM is supported (got {8 * width}-bit); {_CONVERT_HINT}"
        )
    if channels != 1:
        raise InvalidAudioError(f"audio must be mono (got {channels} channels); {_CONVERT_HINT}")
    if rate != TARGET_RATE:
        raise InvalidAudioError(
            f"sample rate must be {TARGET_RATE} Hz (got {rate}); {_CONVERT_HINT}"
        )


def _wav_target(target: str | Path | BinaryIO) -> str | BinaryIO:
    return str(target) if isinstance(target, (str, Path)) else target


def write_wav(target: str | Path | BinaryIO, audio: SynthesizedAudio) -> None:
    """Write mono 16-bit PCM to a WAV file or a binary file-like object."""
    with wave.open(_wav_target(target), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(_BYTES_PER_SAMPLE)
        handle.setframerate(audio.sample_rate)
        handle.writeframes(audio.pcm)


def chunked(audio: AudioChunk, *, chunk_ms: int = 100) -> Iterator[AudioChunk]:
    """Split audio into consecutive chunks of at most ``chunk_ms`` milliseconds."""
    if chunk_ms <= 0:
        raise ValueError(f"chunk_ms must be positive, got {chunk_ms}")
    frame_bytes = _BYTES_PER_SAMPLE * audio.channels
    step = max(1, audio.sample_rate * chunk_ms // 1000) * frame_bytes
    for start in range(0, len(audio.pcm), step):
        yield AudioChunk(
            pcm=audio.pcm[start : start + step],
            sample_rate=audio.sample_rate,
            channels=audio.channels,
        )
