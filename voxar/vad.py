"""Neural voice-activity detection with Silero VAD (optional: ``voxar[vad]`` and a model download).

It decides, frame by frame, whether someone is speaking, which is far more reliable than a volume
threshold in a noisy room. ``onnxruntime`` and ``numpy`` are imported only when it is used. When
the extra or the model is missing, callers fall back to the volume threshold in ``voxar.voice``.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from voxar.config import Config
from voxar.domain import EngineUnavailableError
from voxar.models import CATALOG, ModelStore

MODEL_ID = "silero-vad"
MODEL_FILE = "silero_vad.onnx"
SAMPLE_RATE = 16_000
FRAME_SAMPLES = 512  # the model reads 32 ms at a time at 16 kHz
CONTEXT_SAMPLES = 64  # and also the end of the previous frame
START_PROBABILITY = 0.5  # speech begins at or above this ...
STAY_PROBABILITY = 0.35  # ... and continues while it stays at or above this
_FRAME_BYTES = FRAME_SAMPLES * 2

SpeechTest = Callable[[bytes], bool]


class SileroDetector:
    """One utterance's worth of detector state over a shared model session.

    Call it with 16 kHz mono 16-bit PCM of any length; it says whether that audio contained
    speech. Create a new one per utterance.
    """

    def __init__(self, session: Any) -> None:
        import numpy

        self._np = numpy
        self._session = session
        self._state = numpy.zeros((2, 1, 128), dtype=numpy.float32)
        self._context = numpy.zeros((1, CONTEXT_SAMPLES), dtype=numpy.float32)
        self._rate = numpy.array(SAMPLE_RATE, dtype=numpy.int64)
        self._pending = bytearray()
        self._speaking = False

    def __call__(self, pcm: bytes) -> bool:
        self._pending += pcm
        heard = False
        while len(self._pending) >= _FRAME_BYTES:
            frame = bytes(self._pending[:_FRAME_BYTES])
            del self._pending[:_FRAME_BYTES]
            threshold = STAY_PROBABILITY if self._speaking else START_PROBABILITY
            self._speaking = self._probability(frame) >= threshold
            heard = heard or self._speaking
        return heard or self._speaking

    def _probability(self, frame: bytes) -> float:
        np = self._np
        samples = np.frombuffer(frame, dtype="<i2").astype(np.float32) / 32768.0
        window = np.concatenate([self._context, samples[None, :]], axis=1)
        output, self._state = self._session.run(
            None, {"input": window, "state": self._state, "sr": self._rate}
        )
        self._context = window[:, -CONTEXT_SAMPLES:]
        return float(output[0, 0])


def load_session(model_path: Path) -> Any:
    try:
        import onnxruntime
    except ImportError as exc:
        raise EngineUnavailableError(
            "neural voice detection needs an optional dependency: pip install 'voxar[vad]'"
        ) from exc
    options = onnxruntime.SessionOptions()
    options.inter_op_num_threads = options.intra_op_num_threads = 1  # tiny model: stay light
    return onnxruntime.InferenceSession(
        str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
    )


def detector_factory(config: Config) -> Callable[[], SpeechTest] | None:
    """A factory of fresh detectors, or ``None`` when Silero is not set up (use the volume gate).

    "Not set up" means the extra is not installed or the model was never pulled. An installed
    model that fails its checksum is an error, never a silent fallback.
    """
    spec = CATALOG[MODEL_ID]
    store = ModelStore(config.cache_dir, offline=config.offline)
    if not store.is_installed(spec):
        return None
    store.verify(spec)
    try:
        session = load_session(store.path(spec) / MODEL_FILE)
    except EngineUnavailableError:
        return None
    return lambda: SileroDetector(session)
