"""Real-model tests. Opt-in: ``pytest -m integration`` with torch installed and
``voxar models pull nabra-saudi-7m --accept-license`` done. Behaviour only, not quality or speed."""

import os

import pytest
from voxar.config import Config
from voxar.models import CATALOG, ModelStore
from voxar.testing import SynthesizerContract

from voxar_tts_espeak.engine import MODEL_ID, NabraSynthesizer, create

pytestmark = pytest.mark.integration


def real() -> NabraSynthesizer:
    pytest.importorskip("torch")
    config = Config.from_env(os.environ)
    if not ModelStore(config.cache_dir, offline=True).is_installed(CATALOG[MODEL_ID]):
        pytest.skip(f"model not installed: voxar models pull {MODEL_ID} --accept-license")
    return create(config)


class TestRealNabra(SynthesizerContract):
    make_synthesizer = staticmethod(real)
    sample_text = "مرحبا"  # Arabic engine: Latin-script text is dropped by design


def test_arabic_text_gives_non_silent_24k_audio() -> None:
    audio = real().synthesize("السلام عليكم")
    assert audio.sample_rate == 24_000
    assert len(audio.pcm) > 24_000  # more than half a second of 16-bit samples
    assert any(audio.pcm)


def test_two_sentences_are_longer_than_one() -> None:
    synth = real()
    one = synth.synthesize("مرحبا.")
    two = synth.synthesize("مرحبا. كيف حالك؟")
    assert len(two.pcm) > len(one.pcm)
