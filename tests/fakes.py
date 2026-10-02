"""Test doubles for the ports. No models, no network."""

from collections.abc import Iterable, Iterator

from voxar.domain import AudioChunk, SynthesizedAudio, TranscriptEvent


class FakeRecognizer:
    """Emits one partial and one final event per chunk, text derived from chunk size."""

    def stream(self, chunks: Iterable[AudioChunk]) -> Iterator[TranscriptEvent]:
        for index, chunk in enumerate(chunks):
            yield TranscriptEvent(text=f"part{index}", is_final=False)
            yield TranscriptEvent(text=f"line{index}:{len(chunk.pcm)}", is_final=True)


class FakeSynthesizer:
    """Returns 10 ms of silence per character."""

    def synthesize(self, text: str, *, voice: str | None = None) -> SynthesizedAudio:
        samples = 160 * len(text)
        return SynthesizedAudio(pcm=bytes(2 * samples), sample_rate=16_000)
