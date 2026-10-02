import pytest

from voxar.domain import (
    AudioChunk,
    ConfigError,
    DownloadError,
    EngineUnavailableError,
    InvalidAudioError,
    LicenseNotAcceptedError,
    ModelIntegrityError,
    ModelNotFoundError,
    OfflineModeError,
    SynthesizedAudio,
    VoxarError,
)


def test_audio_chunk_duration() -> None:
    chunk = AudioChunk(pcm=bytes(32_000))  # 16 kHz mono 16-bit: 1 second
    assert chunk.duration_s == 1.0


def test_audio_chunk_rejects_odd_byte_count() -> None:
    with pytest.raises(InvalidAudioError, match="16-bit"):
        AudioChunk(pcm=b"\x00")


@pytest.mark.parametrize("rate", [0, -1])
def test_audio_chunk_rejects_bad_rate(rate: int) -> None:
    with pytest.raises(InvalidAudioError, match="sample rate"):
        AudioChunk(pcm=b"", sample_rate=rate)


def test_audio_chunk_is_immutable() -> None:
    chunk = AudioChunk(pcm=b"")
    with pytest.raises(AttributeError):
        chunk.sample_rate = 8000  # type: ignore[misc]


@pytest.mark.parametrize(
    "error",
    [
        ConfigError,
        DownloadError,
        EngineUnavailableError,
        InvalidAudioError,
        LicenseNotAcceptedError,
        ModelIntegrityError,
        ModelNotFoundError,
        OfflineModeError,
    ],
)
def test_all_errors_share_one_base(error: type[VoxarError]) -> None:
    assert issubclass(error, VoxarError)


def test_audio_chunk_rejects_bad_channel_count() -> None:
    with pytest.raises(InvalidAudioError, match="channels"):
        AudioChunk(pcm=b"", channels=0)


def test_synthesized_audio_validates_rate_and_samples() -> None:
    with pytest.raises(InvalidAudioError, match="sample rate"):
        SynthesizedAudio(pcm=b"", sample_rate=0)
    with pytest.raises(InvalidAudioError, match="16-bit"):
        SynthesizedAudio(pcm=b"\x00", sample_rate=16_000)
