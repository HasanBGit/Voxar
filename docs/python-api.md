# Python API

The public API is what `voxar/__init__.py` exports: `Voxar`, `Config`, the data types `AudioChunk`, `TranscriptEvent` and `SynthesizedAudio`, and the error classes. Everything else is internal.

```python
import os
from voxar import Config, Voxar

app = Voxar.from_config(Config.from_env(os.environ))  # cheap: engines load on first use
print(app.transcribe("sample.wav"))
```

## `Voxar`

| Method | Does |
|---|---|
| `Voxar.from_config(config, registry=None)` | Build from a `Config`. Engines are created lazily, so a missing engine only fails when you use it. |
| `transcribe(path)` | Transcribe a 16 kHz mono 16-bit WAV file and return the final text. The file is checked before any engine is loaded. |
| `transcribe_audio(audio)` | Same, for an already decoded `AudioChunk`. |
| `stream(chunks)` | Transcribe an iterable of `AudioChunk`s, yielding `TranscriptEvent`s: partial ones (`is_final=False`, may still change) and final ones. |
| `speak(text, voice=None)` | Return `SynthesizedAudio` (mono 16-bit PCM). Empty text raises `ValueError`. Needs a synthesizer. |
| `speak_to_file(text, path, voice=None)` | `speak`, then write a WAV file. |
| `warm_up()` | Load the configured engines now. Engines that are not installed are skipped. |

`transcribe` uses 100 ms chunks for audio up to 15 s and 2 s chunks beyond; pass `chunk_ms=` to the `Voxar` constructor to override (the reasons are in [Performance](performance.md)).

You can also pass engines directly: `Voxar(recognizer=..., synthesizer=...)`.

## `Config`

A frozen dataclass: `cache_dir`, `offline`, `recognizer` (default `moonshine`), `synthesizer` (default none). `Config.from_env(env)` reads the `VOXAR_*` variables listed in the [Quickstart](quickstart.md#configuration).

## Errors

Every error voxar raises on purpose derives from `VoxarError`; messages say how to fix the problem.

| Error | Meaning |
|---|---|
| `ConfigError` | invalid configuration or static data |
| `InvalidAudioError` | audio is missing, malformed or not 16 kHz mono 16-bit |
| `ModelNotFoundError` | the model is not installed (`voxar models pull NAME`) |
| `ModelIntegrityError` | a file does not match its pinned SHA-256 |
| `LicenseNotAcceptedError` | install attempted without `--accept-license` |
| `OfflineModeError` | a download was needed while `VOXAR_OFFLINE` is on |
| `EngineUnavailableError` | no usable engine for the request |
| `DownloadError` | a network download failed |

## Writing an engine

An engine implements `SpeechRecognizer` (`stream(chunks) -> events`) or `SpeechSynthesizer` (`synthesize(text, voice=None) -> SynthesizedAudio`) from `voxar.ports`, and is registered through the `voxar.recognizers` or `voxar.synthesizers` entry-point group; the entry point loads a factory that takes a `Config`. Reuse `RecognizerContract` / `SynthesizerContract` from `voxar.testing` in your tests. See [Architecture](../ARCHITECTURE.md).
