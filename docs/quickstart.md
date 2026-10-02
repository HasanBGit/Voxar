# Quickstart

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/HasanBGit/Voxar.git && cd Voxar
uv sync --extra moonshine
uv run voxar models pull moonshine-tiny-streaming-ar --accept-license   # about 31 MB
```

`models pull` shows the model's license and refuses to continue without `--accept-license`. Read [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md) first: the license of this model is MIT according to its upstream repository but **unconfirmed for the file that is downloaded**.

## Transcribe a file

Input must be a 16 kHz mono 16-bit WAV. Anything else is rejected with the command that converts it:

```bash
ffmpeg -i input.m4a -ar 16000 -ac 1 -sample_fmt s16 sample.wav
uv run voxar transcribe sample.wav
```

## Check your setup

```bash
uv run voxar doctor
```

It prints the Python version, the cache directory, and which recognizers and synthesizers are installed.

## Configuration

Environment variables (the only configuration):

| Variable | Meaning | Default |
|---|---|---|
| `VOXAR_CACHE_DIR` | where models are stored | `$XDG_CACHE_HOME/voxar`, else `~/.cache/voxar` |
| `VOXAR_OFFLINE` | `1`/`true` forbids downloads | off |
| `VOXAR_RECOGNIZER` | speech-to-text engine name | `moonshine` |
| `VOXAR_SYNTHESIZER` | text-to-speech engine name | none (set to `nabra-saudi` with the plugin) |

## Use it from Python

```python
from voxar import Config, Voxar
import os

app = Voxar.from_config(Config.from_env(os.environ))
print(app.transcribe("sample.wav"))
```

Engines are created lazily, so `Voxar.from_config` is cheap and a missing engine only fails when you use it.
