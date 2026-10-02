"""Transcribe one WAV file with the Python API.

    uv run python examples/01_transcribe_file.py sample.wav

The file must be 16 kHz mono 16-bit WAV; anything else is rejected with the ffmpeg command that
converts it. Needs: `uv sync --extra moonshine` and `voxar models pull moonshine-tiny-streaming-ar`.
"""

import os
import sys

from voxar import Config, Voxar, VoxarError


def main(path: str) -> int:
    app = Voxar.from_config(Config.from_env(os.environ))  # engines load lazily, on first use
    try:
        print(app.transcribe(path))
    except VoxarError as error:  # every error voxar raises on purpose derives from VoxarError
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    raise SystemExit(main(sys.argv[1]))
