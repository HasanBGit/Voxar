"""Speaking aloud and listening for one utterance: the voice channel between a person and an agent.

Standard library plus a lazy ``sounddevice`` import for the real devices. Everything that can be
tested without hardware is a plain function over audio chunks.
"""

import queue
import re
import sys
import threading
from array import array
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from math import sqrt

from voxar.domain import AudioChunk, EngineUnavailableError, SynthesizedAudio

# Mean absolute level (of 32767) above which a 100 ms block counts as speech. Quiet rooms sit far
# below it; raise it if background noise ends or starts captures wrongly.
SPEECH_LEVEL = 500.0
PRE_ROLL_BLOCKS = 3  # keep a little audio from before the first loud block so no word is clipped
MAX_WAIT_FOR_SPEECH_S = 8.0
PAUSE_BETWEEN_SENTENCES_S = 0.15  # the same gap the Saudi voice leaves inside one synthesis
MIN_SENTENCE_CHARS = 12  # shorter pieces ("نعم.") are joined to a neighbour, not spoken alone
_SENTENCE_END = re.compile(r"(?<=[.!?؟…])\s+|\n+")
_EPSILON = 1e-9  # 10 blocks of 0.1 s add up to 0.9999999999999999, not 1.0

Player = Callable[[SynthesizedAudio], None]
ListenSource = Callable[[], Iterable[AudioChunk]]
SpeechTest = Callable[[bytes], bool]  # does this audio contain speech?


@dataclass(frozen=True)
class VoiceIO:
    """The speakers and microphone, injected so tests and callers never need real devices."""

    play: Player
    listen_chunks: ListenSource
    # Makes a fresh speech test per utterance (a neural detector keeps state); None = volume gate.
    speech_test: Callable[[], SpeechTest] | None = None


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
    is_speech: SpeechTest | None = None,
) -> AudioChunk | None:
    """Collect one spoken phrase: from the first loud block until ``silence_seconds`` of quiet.

    A block is speech if ``is_speech`` says so; without it, if its level reaches ``speech_level``.

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
            loud = is_speech(chunk.pcm) if is_speech else level(chunk.pcm) >= speech_level
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


def split_sentences(text: str) -> list[str]:
    """Break text into sentences to speak one after another; no words are dropped."""
    pieces: list[str] = []
    for part in _SENTENCE_END.split(text.strip()):
        part = part.strip()
        if not part:
            continue
        if pieces and len(pieces[-1]) < MIN_SENTENCE_CHARS:
            pieces[-1] = f"{pieces[-1]} {part}"
        else:
            pieces.append(part)
    if len(pieces) > 1 and len(pieces[-1]) < MIN_SENTENCE_CHARS:
        tail = pieces.pop()
        pieces[-1] = f"{pieces[-1]} {tail}"
    return pieces


def _speakable_sentences(
    sentences: list[str], speak: Callable[[str], SynthesizedAudio]
) -> Iterator[SynthesizedAudio]:
    """Synthesize each sentence, with the pause that follows it. Unspeakable ones are skipped."""
    spoken = False
    for index, sentence in enumerate(sentences):
        try:
            audio = speak(sentence)
        except ValueError as exc:
            if not str(exc).startswith("no speakable text"):
                raise
            if index == len(sentences) - 1 and not spoken:
                raise  # nothing at all was speakable
            continue
        spoken = True
        if index == len(sentences) - 1:
            yield audio
        else:
            pause = bytes(2 * round(PAUSE_BETWEEN_SENTENCES_S * audio.sample_rate))
            yield SynthesizedAudio(audio.pcm + pause, audio.sample_rate)


_Item = tuple[SynthesizedAudio | None, Exception | None]


def _put(ready: "queue.Queue[_Item]", item: _Item, stop: threading.Event) -> bool:
    """Hand an item to the player; give up (False) once the player has stopped listening."""
    while not stop.is_set():
        try:
            ready.put(item, timeout=0.1)
            return True
        except queue.Full:
            continue
    return False


def speak_aloud(speak: Callable[[str], SynthesizedAudio], play: Player, text: str) -> float:
    """Speak ``text`` sentence by sentence: playing one while the next is being synthesized.

    Sound starts after the first sentence is ready instead of after all of them. Returns the
    seconds of speech played. A sentence with nothing speakable is skipped; if no sentence is
    speakable the error is raised, as it would be for the whole text.
    """
    sentences = split_sentences(text) or [text]
    ready: queue.Queue[_Item] = queue.Queue(maxsize=1)
    stop = threading.Event()

    def produce() -> None:
        try:
            for audio in _speakable_sentences(sentences, speak):
                if not _put(ready, (audio, None), stop):
                    return
            _put(ready, (None, None), stop)
        except Exception as exc:  # noqa: BLE001 - raised by the playing thread, not lost here
            _put(ready, (None, exc), stop)

    worker = threading.Thread(target=produce, name="voxar-speech", daemon=True)
    worker.start()
    seconds = 0.0
    try:
        while True:
            audio, failure = ready.get()
            if failure is not None:
                raise failure
            if audio is None:
                return seconds
            play(audio)
            seconds += len(audio.pcm) / 2 / audio.sample_rate
    finally:
        stop.set()  # a failed playback must not leave the worker synthesizing for nobody
        worker.join(timeout=5.0)


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
