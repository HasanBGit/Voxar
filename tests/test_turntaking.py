"""The turn-taking script's measurements are pure functions over synthetic streams: test them."""

# ruff: noqa: S311  (seeded noise for repeatable tests, not security)

import importlib.util
import random
import struct
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "turntaking", Path(__file__).parent.parent / "scripts" / "turntaking.py"
)
assert spec and spec.loader
turntaking = importlib.util.module_from_spec(spec)
spec.loader.exec_module(turntaking)

SPEECH = struct.pack("<h", 3000) * 16_000  # one second of a loud constant tone


def test_a_stream_is_noise_then_speech_then_noise_and_reports_where_speech_ends() -> None:
    stream, speech_end = turntaking.build_stream(SPEECH, 0.0, random.Random(0))
    assert len(stream) / 2 / 16_000 == pytest.approx(1.0 + 1.0 + 4.0)
    assert speech_end == pytest.approx(2.0)


def test_a_stream_without_speech_has_no_speech_end_after_the_lead() -> None:
    stream, speech_end = turntaking.build_stream(None, 0.0, random.Random(0))
    assert len(stream) / 2 / 16_000 == pytest.approx(5.0)
    assert speech_end == pytest.approx(1.0)


def test_the_volume_gate_captures_clean_speech_and_ends_after_the_silence() -> None:
    stream, speech_end = turntaking.build_stream(SPEECH, 0.0, random.Random(0))
    outcome = turntaking.run_once(stream, 1.0, None)
    assert outcome.captured
    assert outcome.stopped_at_s == pytest.approx(speech_end + 1.0, abs=0.11)


def test_loud_noise_fools_the_volume_gate_but_not_a_speech_test() -> None:
    stream, _ = turntaking.build_stream(None, 1500.0, random.Random(0))
    assert turntaking.run_once(stream, 1.0, None).captured  # noise taken for speech
    assert not turntaking.run_once(stream, 1.0, lambda _pcm: False).captured


def test_summary_counts_missed_early_cuts_false_starts_and_the_median_delay() -> None:
    outcome = turntaking.Outcome
    with_speech = [
        (outcome(True, 3.0), 2.0),  # delay 1.0
        (outcome(True, 3.4), 2.0),  # delay 1.4
        (outcome(True, 1.5), 2.0),  # stopped before the speaker finished
        (outcome(False, 6.0), 2.0),  # never captured
    ]
    summary = turntaking.summarize(with_speech, [outcome(True, 5.0), outcome(False, 5.0)])
    assert (summary.runs, summary.missed, summary.cut_early) == (4, 1, 1)
    assert (summary.false_starts, summary.noise_runs) == (1, 2)
    assert summary.median_delay_s == pytest.approx(1.2)


def test_measure_is_repeatable_for_a_seed() -> None:
    a = turntaking.measure([SPEECH], 300.0, 1.0, 2, None, seed=1)
    b = turntaking.measure([SPEECH], 300.0, 1.0, 2, None, seed=1)
    assert a == b


def test_a_clip_with_the_wrong_format_is_rejected(tmp_path: Path) -> None:
    import wave

    path = tmp_path / "bad.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(16_000)
        handle.writeframes(bytes(400))
    with pytest.raises(ValueError, match="16 kHz mono"):
        turntaking.read_clip(path)
