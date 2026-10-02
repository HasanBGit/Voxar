import wave
from pathlib import Path

import pytest

from tests.fakes import FakeRecognizer, FakeSynthesizer
from tests.test_audio import make_wav
from voxar import Voxar
from voxar.config import Config
from voxar.domain import AudioChunk, EngineUnavailableError, InvalidAudioError
from voxar.registry import Registry


def test_transcribe_joins_final_lines_only(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "a.wav", seconds=0.5)
    voxar = Voxar(recognizer=FakeRecognizer(), chunk_ms=250)
    assert voxar.transcribe(wav) == "line0:8000 line1:8000"


def test_stream_yields_partial_and_final_events() -> None:
    voxar = Voxar(recognizer=FakeRecognizer())
    events = list(voxar.stream([AudioChunk(pcm=bytes(4)), AudioChunk(pcm=bytes(4))]))
    assert [e.is_final for e in events] == [False, True, False, True]


def test_transcribe_without_recognizer_fails_fast(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "a.wav")
    with pytest.raises(EngineUnavailableError, match="recognizer"):
        Voxar().transcribe(wav)


def test_speak_without_synthesizer_fails_fast() -> None:
    with pytest.raises(EngineUnavailableError, match="synthesizer"):
        Voxar(recognizer=FakeRecognizer()).speak("hello")


def test_speak_returns_audio() -> None:
    audio = Voxar(synthesizer=FakeSynthesizer()).speak("abc")
    assert len(audio.pcm) == 2 * 160 * 3


def test_speak_to_file(tmp_path: Path) -> None:
    out = tmp_path / "say.wav"
    Voxar(synthesizer=FakeSynthesizer()).speak_to_file("abc", out)
    with wave.open(str(out), "rb") as handle:
        assert handle.getframerate() == 16_000


def test_rejects_empty_text() -> None:
    with pytest.raises(ValueError, match="text"):
        Voxar(synthesizer=FakeSynthesizer()).speak("  ")


def test_from_config_builds_engines_through_registry() -> None:
    registry = Registry(discover=lambda _: {})
    registry.register_recognizer("fake", lambda _: FakeRecognizer())
    registry.register_synthesizer("fake", lambda _: FakeSynthesizer())
    config = Config(cache_dir=Path("/c"), recognizer="fake", synthesizer="fake")
    voxar = Voxar.from_config(config, registry)
    assert voxar.speak("x").sample_rate == 16_000
    assert list(voxar.stream([AudioChunk(pcm=bytes(2))]))


def test_from_config_skips_synthesizer_when_not_configured() -> None:
    registry = Registry(discover=lambda _: {})
    registry.register_recognizer("fake", lambda _: FakeRecognizer())
    config = Config(cache_dir=Path("/c"), recognizer="fake")
    with pytest.raises(EngineUnavailableError, match="synthesizer"):
        Voxar.from_config(config, registry).speak("x")


def test_bad_audio_is_reported_before_any_engine_is_created() -> None:
    created: list[str] = []

    def factory(_: Config) -> FakeRecognizer:
        created.append("recognizer")
        return FakeRecognizer()

    registry = Registry(discover=lambda _: {})
    registry.register_recognizer("fake", factory)
    voxar = Voxar.from_config(Config(cache_dir=Path("/c"), recognizer="fake"), registry)
    with pytest.raises(InvalidAudioError, match="not found"):
        voxar.transcribe("/definitely/missing.wav")
    assert created == []


def test_transcribe_audio_takes_decoded_audio() -> None:
    voxar = Voxar(recognizer=FakeRecognizer(), chunk_ms=250)
    audio = AudioChunk(pcm=bytes(16_000))  # 0.5 s
    assert voxar.transcribe_audio(audio) == "line0:8000 line1:8000"


def first_chunk_bytes(voxar: Voxar, seconds: float) -> int:
    """FakeRecognizer reports each chunk's size as 'lineN:SIZE'; return the first chunk's size."""
    audio = AudioChunk(pcm=bytes(int(seconds * 32_000)))
    return int(voxar.transcribe_audio(audio).split()[0].split(":")[1])


def test_short_audio_is_fed_in_fine_chunks_for_accuracy() -> None:
    assert first_chunk_bytes(Voxar(recognizer=FakeRecognizer()), 10.0) == 3_200  # 100 ms


def test_long_audio_is_fed_in_coarse_chunks_for_speed() -> None:
    assert first_chunk_bytes(Voxar(recognizer=FakeRecognizer()), 20.0) == 64_000  # 2 s


def test_the_threshold_is_fifteen_seconds() -> None:
    voxar = Voxar(recognizer=FakeRecognizer())
    assert first_chunk_bytes(voxar, 15.0) == 3_200
    assert first_chunk_bytes(voxar, 15.5) == 64_000


def test_an_explicit_chunk_size_is_never_overridden() -> None:
    voxar = Voxar(recognizer=FakeRecognizer(), chunk_ms=250)
    assert first_chunk_bytes(voxar, 60.0) == 8_000  # 250 ms, even for long audio


class WarmableRecognizer(FakeRecognizer):
    def __init__(self) -> None:
        self.warmed = 0

    def warm(self) -> None:
        self.warmed += 1


def test_warm_up_loads_every_configured_engine() -> None:
    created: list[str] = []
    recognizer = WarmableRecognizer()
    registry = Registry(discover=lambda _: {})

    def make_recognizer(_: Config) -> WarmableRecognizer:
        created.append("asr")
        return recognizer

    def make_synthesizer(_: Config) -> FakeSynthesizer:
        created.append("tts")
        return FakeSynthesizer()

    registry.register_recognizer("fake", make_recognizer)
    registry.register_synthesizer("fake", make_synthesizer)
    config = Config(cache_dir=Path("/c"), recognizer="fake", synthesizer="fake")
    Voxar.from_config(config, registry).warm_up()
    assert sorted(created) == ["asr", "tts"]
    assert recognizer.warmed == 1


def test_warm_up_skips_engines_that_are_not_installed_instead_of_failing() -> None:
    registry = Registry(discover=lambda _: {})  # nothing registered
    Voxar.from_config(Config(cache_dir=Path("/c")), registry).warm_up()  # does not raise


def test_warm_up_does_not_create_an_engine_twice() -> None:
    created: list[str] = []
    registry = Registry(discover=lambda _: {})

    def make(_: Config) -> FakeRecognizer:
        created.append("asr")
        return FakeRecognizer()

    registry.register_recognizer("fake", make)
    app = Voxar.from_config(Config(cache_dir=Path("/c"), recognizer="fake"), registry)
    app.warm_up()
    app.transcribe_audio(AudioChunk(pcm=bytes(3200)))
    assert created == ["asr"]
