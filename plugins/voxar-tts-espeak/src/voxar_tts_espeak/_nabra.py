"""Torch backend for Nabra-Saudi-7M. Imports torch and the vendored network lazily.

Covered by the opt-in integration test (needs torch and the downloaded model), not by unit tests.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from voxar.domain import EngineUnavailableError

_WEIGHTS = "nabra_saudi_7m.pth"
_CONFIG = "config.json"
_VOICE = "af_msa.pt"
_TATWEEL = "ـ"  # elongation mark; the model was trained without it


@dataclass(frozen=True)
class Backend:
    phonemize: Callable[[str], str]
    render: Callable[[str], list[float]]


def load_backend(model_dir: Path) -> Backend:
    try:
        import torch
        from loguru import logger

        from voxar_tts_espeak._vendor.arabic_g2p import EXTRA_SYMBOLS, ArabicG2P
        from voxar_tts_espeak._vendor.kokoro import KModel
    except ImportError as exc:
        raise EngineUnavailableError(
            "the Saudi TTS engine needs its runtime packages (torch, transformers, misaki, "
            "phonemizer-fork, espeakng-loader): pip install voxar-tts-espeak"
        ) from exc

    logger.disable("voxar_tts_espeak._vendor")  # the vendored code logs configs and phonemes

    model = KModel(
        config=str(model_dir / _CONFIG), model=str(model_dir / _WEIGHTS), disable_complex=True
    ).eval()
    model.vocab.update(EXTRA_SYMBOLS)
    pack = torch.load(model_dir / _VOICE, map_location="cpu", weights_only=True)
    g2p = ArabicG2P(diacritize=False)  # dialect text is used as written, without tashkeel

    def phonemize(text: str) -> str:
        return str(g2p.process(text.replace(_TATWEEL, ""))[1])

    @torch.no_grad()
    def render(phonemes: str) -> list[float]:
        audio = model(phonemes, pack[len(phonemes) - 1], 1.0)
        return list(audio.tolist())

    return Backend(phonemize=phonemize, render=render)
