"""Microphone audio source: 16 kHz mono 16-bit blocks from the default input device."""

import contextlib
import queue
from collections.abc import Iterator

from voxar.audio import TARGET_RATE
from voxar.domain import AudioChunk, EngineUnavailableError, InvalidAudioError

_QUEUE_BLOCKS = 100  # bounded so a slow consumer cannot grow memory without limit


def mic_chunks(
    *, block_ms: int = 100, max_blocks: int | None = None, timeout_s: float = 5.0
) -> Iterator[AudioChunk]:
    """Yield microphone audio until interrupted (Ctrl-C ends the stream cleanly)."""
    try:
        import sounddevice
    except (ImportError, OSError) as exc:
        raise EngineUnavailableError(
            "microphone input needs the sounddevice package and the PortAudio library: "
            "pip install 'voxar[moonshine]'"
        ) from exc

    blocks: queue.Queue[bytes] = queue.Queue(maxsize=_QUEUE_BLOCKS)

    def on_audio(indata: bytes, frames: int, time: object, status: object) -> None:
        with contextlib.suppress(queue.Full):  # drop a block rather than block the audio thread
            blocks.put_nowait(bytes(indata))

    with sounddevice.RawInputStream(
        samplerate=TARGET_RATE,
        channels=1,
        dtype="int16",
        blocksize=TARGET_RATE * block_ms // 1000,
        callback=on_audio,
    ):
        delivered = 0
        try:
            while max_blocks is None or delivered < max_blocks:
                try:
                    yield AudioChunk(pcm=blocks.get(timeout=timeout_s))
                except queue.Empty:
                    raise InvalidAudioError(
                        f"no audio from the microphone for {timeout_s:g} s: "
                        "check the input device and microphone permission"
                    ) from None
                delivered += 1
        except KeyboardInterrupt:
            return
