"""Speak Arabic text to a WAV file with the Saudi voice.

    VOXAR_SYNTHESIZER=nabra-saudi uv run python examples/03_text_to_speech.py \
        "السلام عليكم" hello.wav

Needs the separate GPL-3.0 plugin (`uv pip install -e plugins/voxar-tts-espeak`) and
`voxar models pull nabra-saudi-7m --accept-license`. Output is 24 kHz mono 16-bit.
Write dialect text without full diacritics; Latin-script words are dropped.
"""

import os
import sys

from voxar import Config, Voxar
from voxar.audio import write_wav


def main(text: str, output: str) -> None:
    app = Voxar.from_config(Config.from_env(os.environ))
    audio = app.speak(text)  # synthesize once, keep the audio to report its length
    write_wav(output, audio)
    seconds = len(audio.pcm) / 2 / audio.sample_rate
    print(f"wrote {output}: {seconds:.1f} s at {audio.sample_rate} Hz")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
