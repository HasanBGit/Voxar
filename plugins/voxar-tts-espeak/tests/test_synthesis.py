import pytest

from voxar_tts_espeak.synthesis import (
    MAX_PHONEMES,
    SAMPLE_RATE,
    split_sentences,
    synthesize,
    to_pcm16,
)


def fake_phonemize(text: str) -> str:
    return text.replace(" ", "")  # one phoneme per letter, spaces dropped


def fake_render(phonemes: str) -> list[float]:
    return [0.5] * (10 * len(phonemes))  # 10 samples per phoneme


def test_split_sentences_on_arabic_and_latin_terminators() -> None:
    text = "مرحبا بك. كيف حالك؟ بخير! تمام\nنعم"
    assert split_sentences(text) == ["مرحبا بك.", "كيف حالك؟", "بخير!", "تمام", "نعم"]


def test_split_sentences_ignores_blank_input() -> None:
    assert split_sentences("  \n \n") == []


def test_to_pcm16_scales_and_clamps() -> None:
    pcm = to_pcm16([0.0, 1.0, -1.0, 2.0, -2.0])
    values = [int.from_bytes(pcm[i : i + 2], "little", signed=True) for i in range(0, len(pcm), 2)]
    assert values == [0, 32767, -32767, 32767, -32768]


def test_sample_rate_is_24k() -> None:
    assert SAMPLE_RATE == 24_000


def test_single_sentence_renders_once_without_trailing_pause() -> None:
    audio = synthesize("abc", phonemize=fake_phonemize, render=fake_render, pause_s=1.0)
    assert audio.sample_rate == SAMPLE_RATE
    assert len(audio.pcm) == 2 * 30


def test_sentences_are_joined_with_silence() -> None:
    audio = synthesize("ab. cd.", phonemize=fake_phonemize, render=fake_render, pause_s=0.0005)
    pause_samples = round(0.0005 * SAMPLE_RATE)  # 12
    # "ab." and "cd." are 3 phonemes each -> 30 samples each
    assert len(audio.pcm) == 2 * (30 + pause_samples + 30)


def test_long_sentence_is_split_so_every_chunk_fits_the_model_limit() -> None:
    seen: list[int] = []

    def render(phonemes: str) -> list[float]:
        seen.append(len(phonemes))
        return [0.1]

    word = "a" * 100
    sentence = " ".join([word] * 12)  # 1200 phonemes in one sentence
    synthesize(sentence, phonemize=fake_phonemize, render=render)
    assert len(seen) > 1
    assert all(0 < n <= MAX_PHONEMES for n in seen)
    assert sum(seen) == 1200


def test_a_single_word_longer_than_the_limit_fails_fast() -> None:
    with pytest.raises(ValueError, match="too long"):
        synthesize("a" * (MAX_PHONEMES + 1), phonemize=fake_phonemize, render=fake_render)


def test_text_without_phonemes_fails_fast() -> None:
    with pytest.raises(ValueError, match="speakable"):
        synthesize("hello", phonemize=lambda _: "", render=fake_render)
