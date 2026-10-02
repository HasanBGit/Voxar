import sys
from pathlib import Path

import pytest
from voxar.config import Config
from voxar.domain import EngineUnavailableError, ModelNotFoundError, SynthesizedAudio
from voxar.testing import SynthesizerContract

from voxar_tts_espeak import _nabra
from voxar_tts_espeak.engine import MODEL_ID, VOICES, NabraSynthesizer, create


def make() -> NabraSynthesizer:
    return NabraSynthesizer(phonemize=lambda t: t.replace(" ", ""), render=lambda p: [0.1] * 24)


class TestNabraContract(SynthesizerContract):
    make_synthesizer = staticmethod(make)


def test_default_and_named_voice_work() -> None:
    assert isinstance(make().synthesize("abc"), SynthesizedAudio)
    assert isinstance(make().synthesize("abc", voice=VOICES[0]), SynthesizedAudio)


def test_unknown_voice_lists_available_voices() -> None:
    with pytest.raises(ValueError, match=rf"unknown voice.*{VOICES[0]}"):
        make().synthesize("abc", voice="nope")


def test_create_requires_the_model(tmp_path: Path) -> None:
    with pytest.raises(ModelNotFoundError, match=f"voxar models pull {MODEL_ID}"):
        create(Config(cache_dir=tmp_path))


def test_backend_without_torch_gives_install_hint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(sys.modules, "torch", None)
    with pytest.raises(EngineUnavailableError, match="voxar-tts-espeak"):
        _nabra.load_backend(tmp_path)
