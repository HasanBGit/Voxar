"""Interfaces the core depends on. Engines implement them; the core never imports an engine."""

from collections.abc import Iterable, Iterator
from typing import Protocol, runtime_checkable

from voxar.domain import AudioChunk, SynthesizedAudio, TranscriptEvent


@runtime_checkable
class SpeechRecognizer(Protocol):
    """Streaming speech-to-text.

    Consumes 16 kHz mono 16-bit chunks and yields partial and final events. Silence may
    produce no events; if any are produced, the last one must be final.
    """

    def stream(self, chunks: Iterable[AudioChunk]) -> Iterator[TranscriptEvent]: ...


@runtime_checkable
class SpeechSynthesizer(Protocol):
    """Text-to-speech."""

    def synthesize(self, text: str, *, voice: str | None = None) -> SynthesizedAudio: ...
