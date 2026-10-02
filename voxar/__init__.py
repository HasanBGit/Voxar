"""voxar: dialect-aware on-device speech. Pre-alpha."""

from voxar.api import Voxar
from voxar.config import Config
from voxar.domain import (
    AudioChunk,
    ConfigError,
    DownloadError,
    EngineUnavailableError,
    InvalidAudioError,
    LicenseNotAcceptedError,
    LLMError,
    ModelIntegrityError,
    ModelNotFoundError,
    OfflineModeError,
    SynthesizedAudio,
    TranscriptEvent,
    VoxarError,
)

__version__ = "0.0.1"

__all__ = [
    "AudioChunk",
    "Config",
    "ConfigError",
    "DownloadError",
    "EngineUnavailableError",
    "InvalidAudioError",
    "LLMError",
    "LicenseNotAcceptedError",
    "ModelIntegrityError",
    "ModelNotFoundError",
    "OfflineModeError",
    "SynthesizedAudio",
    "TranscriptEvent",
    "Voxar",
    "VoxarError",
    "__version__",
]
