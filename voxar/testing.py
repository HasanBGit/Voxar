"""Reusable contract every engine adapter must satisfy (shipped so plugins can reuse it).

Subclass, set ``make_recognizer`` / ``make_synthesizer``, and pytest collects the tests.
Real adapters (Moonshine, TTS plugins) reuse this in their own test modules.
"""

from collections.abc import Callable

from voxar.domain import AudioChunk, SynthesizedAudio
from voxar.ports import SpeechRecognizer, SpeechSynthesizer


class RecognizerContract:
    make_recognizer: Callable[[], SpeechRecognizer]

    def test_empty_stream_yields_nothing(self) -> None:
        assert list(self.make_recognizer().stream([])) == []

    def test_events_are_text_and_flag(self) -> None:
        events = list(self.make_recognizer().stream([AudioChunk(pcm=bytes(3200))]))
        assert all(isinstance(e.text, str) and isinstance(e.is_final, bool) for e in events)

    def test_if_any_events_the_last_one_is_final(self) -> None:
        # Silence may legitimately produce no events; speech must end with a final one.
        events = list(self.make_recognizer().stream([AudioChunk(pcm=bytes(3200))]))
        assert not events or events[-1].is_final


class SynthesizerContract:
    make_synthesizer: Callable[[], SpeechSynthesizer]
    sample_text = "hello"  # engines for other languages override this with text they can speak

    def test_returns_pcm16_audio(self) -> None:
        audio = self.make_synthesizer().synthesize(self.sample_text)
        assert isinstance(audio, SynthesizedAudio)
        assert audio.sample_rate > 0
        assert len(audio.pcm) % 2 == 0
