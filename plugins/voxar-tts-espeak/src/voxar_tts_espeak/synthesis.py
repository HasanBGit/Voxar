"""Text to 16-bit PCM using an injected phonemizer and renderer.

No torch and no third-party imports here, so the logic is unit-testable without the model:
sentence splitting, the model's 510-phoneme input limit, silence between pieces, and the
float-to-PCM conversion.
"""

import re
import sys
from array import array
from collections.abc import Callable, Iterable

from voxar.domain import SynthesizedAudio

SAMPLE_RATE = 24_000
MAX_PHONEMES = 510  # Kokoro/StyleTTS2 voice packs have 510 rows, indexed by phoneme count
DEFAULT_PAUSE_S = 0.15

Phonemize = Callable[[str], str]
Render = Callable[[str], Iterable[float]]

_SENTENCE_BREAK = re.compile(r"(?<=[.!?؟])\s+|\n+")


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_BREAK.split(text.strip()) if part.strip()]


def to_pcm16(samples: Iterable[float]) -> bytes:
    pcm = array("h", (max(-32768, min(32767, round(s * 32767))) for s in samples))
    if sys.byteorder == "big":
        pcm.byteswap()
    return pcm.tobytes()


def _phoneme_chunks(sentence: str, phonemize: Phonemize) -> list[str]:
    """Phoneme strings for one sentence, each short enough for the model."""
    whole = phonemize(sentence)
    if len(whole) <= MAX_PHONEMES:
        return [whole] if whole.strip() else []
    chunks: list[str] = []
    current: list[str] = []
    for word in sentence.split():
        candidate = [*current, word]
        if len(phonemize(" ".join(candidate))) <= MAX_PHONEMES:
            current = candidate
            continue
        if not current:
            raise ValueError(f"a single word is too long to synthesize: {word[:20]!r}...")
        chunks.append(phonemize(" ".join(current)))
        current = [word]
    chunks.append(phonemize(" ".join(current)))
    return [chunk for chunk in chunks if chunk.strip()]


def synthesize(
    text: str,
    *,
    phonemize: Phonemize,
    render: Render,
    sample_rate: int = SAMPLE_RATE,
    pause_s: float = DEFAULT_PAUSE_S,
) -> SynthesizedAudio:
    pieces = [
        phonemes
        for sentence in split_sentences(text)
        for phonemes in _phoneme_chunks(sentence, phonemize)
    ]
    if not pieces:
        raise ValueError("no speakable text: Latin-script words and symbols are dropped")
    silence = [0.0] * round(pause_s * sample_rate)
    samples: list[float] = []
    for index, phonemes in enumerate(pieces):
        if index:
            samples.extend(silence)
        samples.extend(render(phonemes))
    return SynthesizedAudio(pcm=to_pcm16(samples), sample_rate=sample_rate)
