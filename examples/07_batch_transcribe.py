"""Transcribe every WAV in a folder to a JSONL file, with timing per file.

    uv run python examples/07_batch_transcribe.py recordings/ transcripts.jsonl

One line per file: {"file", "seconds", "took", "rtf", "text"} (rtf = took / seconds; below 1.0 is
faster than real time). A bad file is recorded as {"file", "error"} and the batch continues.
"""

import json
import os
import sys
import time
from pathlib import Path

from voxar import Config, Voxar, VoxarError
from voxar.audio import read_wav


def main(folder: Path, output: Path) -> None:
    app = Voxar.from_config(Config.from_env(os.environ))
    with output.open("w", encoding="utf-8") as out:
        for wav in sorted(folder.glob("*.wav")):
            try:
                seconds = read_wav(wav).duration_s
                started = time.perf_counter()
                text = app.transcribe(wav)
                took = time.perf_counter() - started
                row = {
                    "file": wav.name,
                    "seconds": round(seconds, 2),
                    "took": round(took, 2),
                    "rtf": round(took / seconds, 3),
                    "text": text,
                }
            except VoxarError as error:
                row = {"file": wav.name, "error": str(error)}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(row.get("error") or f"{wav.name}: {row['text'][:50]}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
