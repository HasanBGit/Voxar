"""Say a sentence, then transcribe your own speech back: a quick end-to-end check of both engines.

    VOXAR_SYNTHESIZER=nabra-saudi uv run python examples/08_round_trip.py "يا أهلاً وسهلاً"

Needs both engines installed in one environment (the TTS plugin and `voxar[moonshine]`).
The synthesized audio is 24 kHz, so it is resampled to 16 kHz with ffmpeg (must be installed).
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from voxar import Config, Voxar


def main(text: str) -> None:
    app = Voxar.from_config(Config.from_env(os.environ))
    with tempfile.TemporaryDirectory() as folder:
        spoken, converted = Path(folder, "say.wav"), Path(folder, "say16k.wav")
        app.speak_to_file(text, spoken)
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-i", spoken, "-ar", "16000", "-ac", "1", converted],
            check=True,
        )
        print("said:      ", text)
        print("heard back:", app.transcribe(converted))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
