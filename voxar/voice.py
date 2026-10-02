"""Speaking aloud and listening for one utterance: the voice channel between a person and an agent.

Standard library plus a lazy ``sounddevice`` import for the real devices. Everything that can be
tested without hardware is a plain function over audio chunks.
"""

import sys
from array import array
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from math import sqrt

from voxar.domain import AudioChunk, EngineUnavailableError, SynthesizedAudio

# Mean absolute level (of 32767) above which a 100 ms block counts as speech. Quiet rooms sit far
# below it; raise it if background noise ends or starts captures wrongly.
SPEECH_LEVEL = 500.0
PRE_ROLL_BLOCKS = 3  # keep a little audio from before the first loud block so no word is clipped
MAX_WAIT_FOR_SPEECH_S = 8.0
_EPSILON = 1e-9  # 10 blocks of 0.1 s add up to 0.9999999999999999, not 1.0

Player = Callable[[SynthesizedAudio], None]
ListenSource = Callable[[], Iterable[AudioChunk]]


@dataclass(frozen=True)
class VoiceIO:
    """The speakers and microphone, injected so tests and callers never need real devices."""

    play: Player
    listen_chunks: ListenSource


def level(pcm: bytes) -> float:
    """Root-mean-square amplitude of 16-bit PCM (0 for silence, up to 32767)."""
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder == "big":
        samples.byteswap()
    if not samples:
        return 0.0
    return sqrt(sum(s * s for s in samples) / len(samples))


def record_utterance(
    chunks: Iterable[AudioChunk],
    *,
    max_seconds: float,
    silence_seconds: float,
    wait_seconds: float = MAX_WAIT_FOR_SPEECH_S,
    speech_level: float = SPEECH_LEVEL,
) -> AudioChunk | None:
    """Collect one spoken phrase: from the first loud block until ``silence_seconds`` of quiet.

    Returns ``None`` when nobody spoke within ``wait_seconds`` (capped by ``max_seconds``). The
    phrase is cut off at ``max_seconds`` in total. The source is closed as soon as we stop, which
    releases the microphone.
    """
    wait = min(wait_seconds, max_seconds)
    before: deque[bytes] = deque(maxlen=PRE_ROLL_BLOCKS)
    kept: list[bytes] = []
    elapsed = quiet = 0.0
    heard = False
    try:
        for chunk in chunks:
            elapsed += chunk.duration_s
            loud = level(chunk.pcm) >= speech_level
            if loud and not heard:
                heard = True
                kept.extend(before)
            if heard:
                kept.append(chunk.pcm)
                quiet = 0.0 if loud else quiet + chunk.duration_s
                if quiet >= silence_seconds - _EPSILON or elapsed >= max_seconds - _EPSILON:
                    break
            else:
                before.append(chunk.pcm)
                if elapsed >= wait - _EPSILON:
                    break
    finally:
        close = getattr(chunks, "close", None)
        if callable(close):
            close()
    return AudioChunk(pcm=b"".join(kept)) if kept else None


def play_audio(audio: SynthesizedAudio) -> None:
    """Play mono 16-bit audio on the default output device and return when it has finished."""
    try:
        import sounddevice
    except (ImportError, OSError) as exc:
        raise EngineUnavailableError(
            "playing audio needs the sounddevice package and the PortAudio library: "
            "pip install 'voxar[moonshine]'"
        ) from exc
    with sounddevice.RawOutputStream(
        samplerate=audio.sample_rate, channels=1, dtype="int16"
    ) as stream:
        stream.write(audio.pcm)
