"""Real Silero model: opt-in (``pytest -m integration``), skipped when it is not installed."""

import os

import pytest

from voxar.config import Config
from voxar.vad import detector_factory

pytest.importorskip("onnxruntime")
np = pytest.importorskip("numpy")

pytestmark = pytest.mark.integration


def test_the_real_model_hears_no_speech_in_quiet_noise() -> None:
    factory = detector_factory(Config.from_env(os.environ))
    if factory is None:
        pytest.skip("run: voxar models pull silero-vad --accept-license")
    detector = factory()
    noise = (np.random.default_rng(0).standard_normal(16000) * 100).astype("<i2").tobytes()
    assert detector(noise) is False
