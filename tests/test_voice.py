"""Voice capture is pure logic over chunks: test it with synthetic loud and quiet blocks."""

import struct
import threading
from collections.abc import Iterator

import pytest

from voxar.domain import AudioChunk, EngineUnavailableError, SynthesizedAudio
from voxar.voice import level, play_audio, record_utterance, speak_aloud, split_sentences

BLOCK = 1600  # 100 ms at 16 kHz


def loud(amplitude: int = 3000) -> AudioChunk:
    return AudioChunk(pcm=struct.pack("<h", amplitude) * BLOCK)


def quiet() -> AudioChunk:
    return AudioChunk(pcm=bytes(2 * BLOCK))


def test_level_is_zero_for_silence_and_the_amplitude_for_a_constant_tone() -> None:
    assert level(bytes(200)) == 0.0
    assert level(b"") == 0.0
    assert level(struct.pack("<h", -2000) * 50) == pytest.approx(2000)


def test_a_phrase_ends_after_the_silence_and_includes_it() -> None:
    chunks = [quiet(), loud(), loud(), quiet(), quiet(), quiet(), loud()]  # last is never read
    audio = record_utterance(iter(chunks), max_seconds=10, silence_seconds=0.3)
    assert audio is not None
    # 1 pre-roll block + 2 loud + 3 quiet blocks; the stray loud block after the pause is ignored
    assert len(audio.pcm) == 6 * BLOCK * 2


def test_pre_roll_is_limited_to_three_blocks() -> None:
    chunks = [quiet()] * 10 + [loud(), quiet(), quiet()]
    audio = record_utterance(iter(chunks), max_seconds=10, silence_seconds=0.2)
    assert audio is not None
    assert len(audio.pcm) == (3 + 1 + 2) * BLOCK * 2


def test_nobody_speaking_returns_none_after_the_wait() -> None:
    read = []

    def source() -> Iterator[AudioChunk]:
        for _ in range(1000):
            read.append(1)
            yield quiet()

    assert record_utterance(source(), max_seconds=30, silence_seconds=1, wait_seconds=1.0) is None
    assert len(read) == 10  # stopped after 1.0 s of silence, not after 1000 blocks


def test_a_long_phrase_is_cut_off_at_max_seconds() -> None:
    audio = record_utterance(iter([loud()] * 100), max_seconds=2.0, silence_seconds=1.5)
    assert audio is not None
    assert audio.duration_s == pytest.approx(2.0)


def test_the_source_is_closed_so_the_microphone_is_released() -> None:
    closed = []

    def source() -> Iterator[AudioChunk]:
        try:
            while True:
                yield loud()
        finally:
            closed.append(True)

    record_utterance(source(), max_seconds=1.0, silence_seconds=1.0)
    assert closed == [True]


def test_wait_cannot_exceed_max_seconds() -> None:
    chunks = iter([quiet()] * 50)
    assert record_utterance(chunks, max_seconds=1.0, silence_seconds=1.0, wait_seconds=8.0) is None
    assert len(list(chunks)) == 40  # 10 blocks consumed, not 50


def test_playing_audio_without_the_audio_library_gives_an_install_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    monkeypatch.setitem(sys.modules, "sounddevice", None)
    with pytest.raises(EngineUnavailableError, match="voxar\\[moonshine\\]"):
        play_audio(SynthesizedAudio(pcm=bytes(100), sample_rate=24_000))


# --- speaking sentence by sentence ---


def audio(seconds: float = 1.0) -> SynthesizedAudio:
    return SynthesizedAudio(pcm=bytes(2 * 16_000 * round(seconds)), sample_rate=16_000)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("مرحبا بكم في الاجتماع. كيف حالكم اليوم؟", ["مرحبا بكم في الاجتماع.", "كيف حالكم اليوم؟"]),
        (
            "سطر أول طويل بما يكفي\nسطر ثان طويل بما يكفي",
            ["سطر أول طويل بما يكفي", "سطر ثان طويل بما يكفي"],
        ),
        ("نعم. تم الانتهاء من كل الاختبارات بنجاح.", ["نعم. تم الانتهاء من كل الاختبارات بنجاح."]),
        ("تم الانتهاء من كل الاختبارات بنجاح. شكرا", ["تم الانتهاء من كل الاختبارات بنجاح. شكرا"]),
        ("  ", []),
        ("بلا علامات ترقيم", ["بلا علامات ترقيم"]),
    ],
)
def test_text_is_split_into_sentences_without_losing_words(text: str, expected: list[str]) -> None:
    assert split_sentences(text) == expected


def test_each_sentence_is_played_in_order_with_a_pause_after_all_but_the_last() -> None:
    played: list[SynthesizedAudio] = []
    seconds = speak_aloud(
        lambda _sentence: audio(1.0), played.append, "جملة أولى طويلة هنا. جملة ثانية طويلة هنا."
    )
    assert len(played) == 2
    assert len(played[0].pcm) > len(played[1].pcm)  # the first carries the pause
    assert seconds == pytest.approx(2.15)


def test_the_next_sentence_is_synthesized_while_the_previous_one_plays() -> None:
    log: list[str] = []
    second_started = threading.Event()

    def speak(sentence: str) -> SynthesizedAudio:
        log.append(f"synth {sentence.split()[0]}")
        if sentence.startswith("ثانية"):
            second_started.set()
        return audio()

    def play(_audio: SynthesizedAudio) -> None:
        if not second_started.is_set():  # while "playing" the first, the second must get ready
            assert second_started.wait(timeout=5.0)
        log.append("play")

    speak_aloud(speak, play, "أولى جملة طويلة هنا. ثانية جملة طويلة هنا.")
    assert log == ["synth أولى", "synth ثانية", "play", "play"]


def test_a_sentence_with_nothing_speakable_is_skipped_not_fatal() -> None:
    def speak(sentence: str) -> SynthesizedAudio:
        if sentence.startswith("OK"):
            raise ValueError("no speakable text: Latin-script words and symbols are dropped")
        return audio()

    played: list[SynthesizedAudio] = []
    speak_aloud(speak, played.append, "جملة عربية طويلة هنا. OK this is english only.")
    assert len(played) == 1


def test_text_with_nothing_speakable_raises_the_engine_error() -> None:
    def speak(_sentence: str) -> SynthesizedAudio:
        raise ValueError("no speakable text: Latin-script words and symbols are dropped")

    with pytest.raises(ValueError, match="no speakable text"):
        speak_aloud(speak, lambda _a: None, "only english here. and more english.")


def test_a_real_synthesis_error_is_raised_after_what_was_ready_has_played() -> None:
    def speak(sentence: str) -> SynthesizedAudio:
        if sentence.startswith("ثانية"):
            raise RuntimeError("engine crashed")
        return audio()

    played: list[SynthesizedAudio] = []
    with pytest.raises(RuntimeError, match="engine crashed"):
        speak_aloud(speak, played.append, "أولى جملة طويلة هنا. ثانية جملة طويلة هنا.")
    assert len(played) == 1


def test_a_failed_playback_stops_the_synthesis_worker() -> None:
    def play(_audio: SynthesizedAudio) -> None:
        raise OSError("no output device")

    before = threading.active_count()
    with pytest.raises(OSError, match="no output device"):
        speak_aloud(
            lambda _s: audio(),
            play,
            "جملة أولى طويلة هنا. جملة ثانية طويلة هنا. جملة ثالثة طويلة هنا.",
        )
    assert threading.active_count() == before  # no thread left synthesizing for nobody
