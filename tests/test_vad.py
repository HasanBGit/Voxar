"""The detector's framing and hysteresis, tested with a scripted model session (no model file)."""

from pathlib import Path
from typing import Any

import pytest

from voxar.config import Config
from voxar.domain import AudioChunk
from voxar.models import CATALOG
from voxar.vad import FRAME_SAMPLES, MODEL_ID, SileroDetector, detector_factory
from voxar.voice import record_utterance

np = pytest.importorskip("numpy")

FRAME = bytes(2 * FRAME_SAMPLES)
BLOCK = bytes(3200)  # 100 ms of 16 kHz 16-bit audio: three whole frames and a remainder


class ScriptedSession:
    """Returns the next scripted speech probability for every frame it is asked about."""

    def __init__(self, probabilities: list[float]) -> None:
        self._probabilities = iter(probabilities)
        self.windows: list[Any] = []

    def run(self, _outputs: Any, feed: dict[str, Any]) -> tuple[Any, Any]:
        self.windows.append(feed["input"])
        return np.array([[next(self._probabilities)]], dtype=np.float32), feed["state"]


def test_speech_starts_at_the_start_probability_and_not_below_it() -> None:
    detector = SileroDetector(ScriptedSession([0.49, 0.5]))
    assert detector(FRAME) is False
    assert detector(FRAME) is True


def test_speech_stays_on_until_the_probability_drops_below_the_stay_level() -> None:
    detector = SileroDetector(ScriptedSession([0.9, 0.4, 0.34]))
    assert detector(FRAME) is True
    assert detector(FRAME) is True  # 0.4 is below the start level but above the stay level
    assert detector(FRAME) is False


def test_audio_that_is_not_a_whole_number_of_frames_is_carried_over() -> None:
    session = ScriptedSession([0.0] * 10)
    detector = SileroDetector(session)
    for _ in range(3):
        detector(BLOCK)  # 3 x 1600 samples = 9 whole frames and 192 samples left over
    assert len(session.windows) == 9
    assert all(window.shape == (1, 64 + FRAME_SAMPLES) for window in session.windows)


def test_a_block_counts_as_speech_if_any_frame_in_it_was_speech() -> None:
    detector = SileroDetector(ScriptedSession([0.0, 0.9, 0.0]))
    assert detector(BLOCK) is True  # a middle frame spoke even though the last one did not


def test_each_frame_sees_the_end_of_the_previous_one_as_context() -> None:
    session = ScriptedSession([0.0, 0.0])
    detector = SileroDetector(session)
    detector(np.arange(FRAME_SAMPLES, dtype="<i2").tobytes() * 2)
    first, second = session.windows
    assert second[0, :64].tolist() == first[0, -64:].tolist()


def test_record_utterance_follows_the_detector_instead_of_the_volume() -> None:
    # Loud noise that is not speech must neither start nor extend a phrase.
    loud_noise = AudioChunk(pcm=(b"\xb8\x0b" * 1600))
    verdicts = iter([False, True, True, False, False, False, True])
    audio = record_utterance(
        iter([loud_noise] * 7),
        max_seconds=10,
        silence_seconds=0.3,
        is_speech=lambda _pcm: next(verdicts),
    )
    assert audio is not None
    # one block of pre-roll, two spoken blocks, then three quiet ones end it; the 7th is never read
    assert audio.duration_s == pytest.approx(0.6)


def test_without_the_model_or_the_extra_the_factory_returns_none(tmp_path: Path) -> None:
    assert detector_factory(Config(cache_dir=tmp_path)) is None


def test_the_catalog_pins_the_model_by_hash() -> None:
    spec = CATALOG[MODEL_ID]
    assert spec.license == "MIT"
    assert [f.name for f in spec.files] == ["silero_vad.onnx"]
