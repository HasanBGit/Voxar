"""Immutable data types and the error hierarchy. No I/O, no third-party imports."""

from dataclasses import dataclass

_BYTES_PER_SAMPLE = 2  # 16-bit PCM


class VoxarError(Exception):
    """Base class for every error voxar raises on purpose."""


class ConfigError(VoxarError):
    """Invalid configuration or invalid static data."""


class InvalidAudioError(VoxarError):
    """Audio input is missing, malformed or in an unsupported format."""


class ModelNotFoundError(VoxarError):
    """A required model is not installed."""


class ModelIntegrityError(VoxarError):
    """A model file does not match its pinned SHA-256."""


class LicenseNotAcceptedError(VoxarError):
    """The user has not accepted the license of a model they are installing."""


class OfflineModeError(VoxarError):
    """An operation needs the network but offline mode is on."""


class EngineUnavailableError(VoxarError):
    """No usable engine for the requested capability."""


class DownloadError(VoxarError):
    """A network download failed."""


class LLMError(VoxarError):
    """A language-model request failed or returned something unusable."""


def _check_pcm16(pcm: bytes, channels: int) -> None:
    frame = _BYTES_PER_SAMPLE * channels
    if len(pcm) % frame:
        raise InvalidAudioError(
            f"PCM data must be whole 16-bit samples "
            f"(got {len(pcm)} bytes for {channels} channel(s))"
        )


@dataclass(frozen=True)
class AudioChunk:
    """A piece of 16-bit little-endian PCM audio."""

    pcm: bytes
    sample_rate: int = 16_000
    channels: int = 1

    def __post_init__(self) -> None:
        if self.sample_rate <= 0:
            raise InvalidAudioError(f"sample rate must be positive, got {self.sample_rate}")
        if self.channels <= 0:
            raise InvalidAudioError(f"channels must be positive, got {self.channels}")
        _check_pcm16(self.pcm, self.channels)

    @property
    def duration_s(self) -> float:
        frames = len(self.pcm) // (_BYTES_PER_SAMPLE * self.channels)
        return frames / self.sample_rate


@dataclass(frozen=True)
class TranscriptEvent:
    """Recognizer output. ``is_final`` is False for in-progress text that may still change."""

    text: str
    is_final: bool


@dataclass(frozen=True)
class SynthesizedAudio:
    """Mono 16-bit PCM produced by a synthesizer."""

    pcm: bytes
    sample_rate: int

    def __post_init__(self) -> None:
        if self.sample_rate <= 0:
            raise InvalidAudioError(f"sample rate must be positive, got {self.sample_rate}")
        _check_pcm16(self.pcm, 1)
