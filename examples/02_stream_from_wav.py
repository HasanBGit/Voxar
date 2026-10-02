"""Stream a WAV file in 100 ms chunks, like a live microphone, and print events as they arrive.

    uv run python examples/02_stream_from_wav.py sample.wav

Partial events ("final": False) can still change; a final event never does. This is the same
loop you would run on microphone audio (see `voxar listen`, or voxar.mic.mic_chunks()).
"""

import os
import sys

from voxar import Config, Voxar
from voxar.audio import chunked, read_wav


def main(path: str) -> None:
    app = Voxar.from_config(Config.from_env(os.environ))
    for event in app.stream(chunked(read_wav(path), chunk_ms=100)):
        kind = "final  " if event.is_final else "partial"
        print(f"{kind} {event.text}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
