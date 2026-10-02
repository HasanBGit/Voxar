"""The ``nabra-saudi`` synthesizer: Saudi-dialect Arabic TTS (Nabra-Saudi-7M, single voice)."""

from voxar.config import Config
from voxar.domain import SynthesizedAudio
from voxar.models import CATALOG, ModelStore

from voxar_tts_espeak._nabra import load_backend
from voxar_tts_espeak.synthesis import Phonemize, Render, synthesize

MODEL_ID = "nabra-saudi-7m"
VOICES = ("af_msa",)


class NabraSynthesizer:
    def __init__(self, phonemize: Phonemize, render: Render) -> None:
        self._phonemize = phonemize
        self._render = render

    def synthesize(self, text: str, *, voice: str | None = None) -> SynthesizedAudio:
        if voice is not None and voice not in VOICES:
            raise ValueError(f"unknown voice {voice!r}; available: {', '.join(VOICES)}")
        return synthesize(text, phonemize=self._phonemize, render=self._render)


def create(config: Config) -> NabraSynthesizer:
    """Entry-point factory: verifies the installed model, then loads the torch backend."""
    spec = CATALOG[MODEL_ID]
    store = ModelStore(config.cache_dir, offline=config.offline)
    store.verify(spec)
    backend = load_backend(store.path(spec))
    return NabraSynthesizer(backend.phonemize, backend.render)
