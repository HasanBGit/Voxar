"""The public facade. Depends only on ports; engines arrive by injection or the registry."""

from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

from voxar.audio import chunked, read_wav, write_wav
from voxar.config import Config
from voxar.domain import (
    AudioChunk,
    EngineUnavailableError,
    SynthesizedAudio,
    TranscriptEvent,
    VoxarError,
)
from voxar.ports import SpeechRecognizer, SpeechSynthesizer
from voxar.registry import Registry

# Measured on this project's synthetic Arabic corpus (see CHANGELOG): up to ~15 s, fine chunks are
# clearly more accurate; beyond it coarse chunks are as accurate and 1.5-3x faster, and the cost of
# fine chunks keeps growing with length.
LONG_AUDIO_SECONDS = 15.0
FINE_CHUNK_MS = 100
COARSE_CHUNK_MS = 2000


class Voxar:
    def __init__(
        self,
        recognizer: SpeechRecognizer | None = None,
        synthesizer: SpeechSynthesizer | None = None,
        *,
        chunk_ms: int | None = None,
    ) -> None:
        self._recognizer = recognizer
        self._synthesizer = synthesizer
        self._recognizer_provider: Callable[[], SpeechRecognizer] | None = None
        self._synthesizer_provider: Callable[[], SpeechSynthesizer] | None = None
        self._chunk_ms = chunk_ms

    @classmethod
    def from_config(cls, config: Config, registry: Registry | None = None) -> "Voxar":
        """Build from configuration. Engines are created lazily, only when first used."""
        reg = registry or Registry()
        voxar = cls()
        voxar._recognizer_provider = lambda: reg.recognizer(config.recognizer, config)
        if config.synthesizer:
            name = config.synthesizer
            voxar._synthesizer_provider = lambda: reg.synthesizer(name, config)
        return voxar

    def warm_up(self) -> None:
        """Load the configured engines now, so the first request does not pay the start-up cost.

        Engines that are not installed (or whose model is not pulled) are skipped: warming up is
        an optimization and must never stop a server from starting.
        """
        for require in (self._require_recognizer, self._require_synthesizer):
            try:
                engine = require()
            except VoxarError:
                continue
            warm = getattr(engine, "warm", None)
            if callable(warm):
                warm()

    def transcribe(self, path: str | Path) -> str:
        """Transcribe a 16 kHz mono 16-bit WAV file and return the final text."""
        audio = read_wav(path)  # cheap input check first: do not load an engine for a bad file
        return self.transcribe_audio(audio)

    def transcribe_audio(self, audio: AudioChunk) -> str:
        """Transcribe already-decoded 16 kHz mono audio and return the final text."""
        recognizer = self._require_recognizer()
        events = recognizer.stream(chunked(audio, chunk_ms=self._chunk_ms_for(audio)))
        return " ".join(event.text for event in events if event.is_final)

    def _chunk_ms_for(self, audio: AudioChunk) -> int:
        """An explicit chunk size wins; otherwise fine chunks for short audio, coarse for long."""
        if self._chunk_ms is not None:
            return self._chunk_ms
        return COARSE_CHUNK_MS if audio.duration_s > LONG_AUDIO_SECONDS else FINE_CHUNK_MS

    def stream(self, chunks: Iterable[AudioChunk]) -> Iterator[TranscriptEvent]:
        """Transcribe a live stream of chunks, yielding partial and final events."""
        return self._require_recognizer().stream(chunks)

    def speak(self, text: str, *, voice: str | None = None) -> SynthesizedAudio:
        if not text.strip():
            raise ValueError("text must not be empty")
        return self._require_synthesizer().synthesize(text, voice=voice)

    def speak_to_file(self, text: str, path: str | Path, *, voice: str | None = None) -> None:
        write_wav(path, self.speak(text, voice=voice))

    def _require_recognizer(self) -> SpeechRecognizer:
        if self._recognizer is None and self._recognizer_provider is not None:
            self._recognizer = self._recognizer_provider()
        if self._recognizer is None:
            raise EngineUnavailableError(
                "no recognizer configured: set VOXAR_RECOGNIZER or pass one"
            )
        return self._recognizer

    def _require_synthesizer(self) -> SpeechSynthesizer:
        if self._synthesizer is None and self._synthesizer_provider is not None:
            self._synthesizer = self._synthesizer_provider()
        if self._synthesizer is None:
            raise EngineUnavailableError(
                "no synthesizer configured: set VOXAR_SYNTHESIZER (needs a TTS engine package)"
            )
        return self._synthesizer
