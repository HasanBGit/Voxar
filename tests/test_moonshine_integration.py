"""Real-model tests. Opt-in: ``pytest -m integration`` after
``voxar models pull moonshine-tiny-streaming-ar --accept-license``.
They check behaviour (the port contract), not accuracy or speed."""

import os

import pytest

from voxar.config import Config
from voxar.engines.moonshine import MODEL_ID, MoonshineRecognizer, create
from voxar.models import CATALOG, ModelStore
from voxar.testing import RecognizerContract

pytestmark = pytest.mark.integration


def real_recognizer() -> MoonshineRecognizer:
    pytest.importorskip("moonshine_voice")
    config = Config.from_env(os.environ)
    if not ModelStore(config.cache_dir, offline=True).is_installed(CATALOG[MODEL_ID]):
        pytest.skip("model not installed: voxar models pull moonshine-tiny-streaming-ar")
    return create(config)


class TestRealMoonshine(RecognizerContract):
    make_recognizer = staticmethod(real_recognizer)
