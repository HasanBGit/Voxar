# voxar-tts-espeak

Saudi-dialect text-to-speech engine for [voxar](../../README.md). It registers a synthesizer named `nabra-saudi` (single voice `af_msa`) using the Nabra-Saudi-7M model.

> **License: GPL-3.0-only.** This is a separate package on purpose. Its runtime uses `espeak-ng` and `phonemizer-fork` (both GPL-3.0; the `espeakng-loader` wheel bundles the espeak-ng library), so the combined work is GPL-3.0. The voxar core and ASR stay Apache-2.0 and never import this package. See [ADR 0002](../../docs/adr/0002-license-split.md). The Nabra model weights are Apache-2.0. This is not legal advice.

> **Status: pre-alpha.** Needs torch and transformers (a heavy install). It is a desktop/server path, not the low-end-device path; that is the planned ONNX export.

## Use

```bash
uv pip install -e plugins/voxar-tts-espeak        # installs torch, transformers, misaki, ...
voxar models pull nabra-saudi-7m --accept-license  # ~31 MB, SHA-256 pinned
VOXAR_SYNTHESIZER=nabra-saudi voxar say "السلام عليكم" -o hello.wav
```

Write dialect text as people write it, without full tashkeel (diacritics make this model worse). Latin-script words are dropped. Output is 24 kHz mono 16-bit WAV.

## What is inside

- `synthesis.py`: sentence splitting, the model's 510-phoneme limit, pauses, PCM conversion. No third-party imports; fully unit-tested.
- `engine.py`: the `nabra-saudi` synthesizer and the entry-point factory (verifies the model's checksums first).
- `_nabra.py`: the torch backend (opt-in integration test).
- `_vendor/`: reviewed, minimally patched third-party code from the Nabra-Saudi-7M repo. See [`_vendor/UPSTREAM.md`](src/voxar_tts_espeak/_vendor/UPSTREAM.md). We vendor it so no remote code is ever executed.

## Development

```bash
uv venv .venv && uv pip install --no-deps -e . -e ../.. pytest pytest-cov ruff mypy
uv run --no-sync pytest        # unit tests need no torch and no model
uv run --no-sync pytest -m integration   # needs torch + the pulled model
```
