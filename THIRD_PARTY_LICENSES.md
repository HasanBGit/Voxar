# Third-party licenses

Policy: each component keeps its upstream license. We do not relicense anything. Before any release, re-check every row against the upstream source.

Checked 2026-10-02 against the model cards, Hugging Face API and Moonshine's `LICENSE`.

## Components

| Component | Source | License | How it would be used | Notes |
|---|---|---|---|---|
| Moonshine streaming Arabic Tiny | https://huggingface.co/moonshine-ai/moonshine-streaming-tiny-ar (CDN artifact: https://download.moonshine.ai/model/tiny-streaming-ar/quantized_26_08_24) | MIT per upstream `LICENSE` and the Hugging Face card; **unconfirmed for the CDN artifact** (see note below) | ASR engine (downloaded by `voxar models pull`), fine-tune target | Copyright (c) 2025 Useful Sensors, Inc. (dba Moonshine AI). |
| Moonshine runtime / library | https://github.com/moonshine-ai/moonshine | MIT | On-device inference | The repo's MIT covers code outside `core/third-party`. |
| Nabra-Saudi-7M | https://huggingface.co/oddadmix/Nabra-Saudi-7M @ `ef45d882f20355767190dffb2a34393ed1df74fa` | Apache-2.0 | TTS model, run by the GPL-3.0 plugin `voxar-tts-espeak`; weights downloaded by `voxar models pull nabra-saudi-7m` with pinned SHA-256 | Weights load with `torch.load(weights_only=True)`. Its patched Kokoro code is vendored (reviewed, network fallbacks removed) in the plugin; see `plugins/voxar-tts-espeak/src/voxar_tts_espeak/_vendor/UPSTREAM.md`. The voice's speaker consent is not documented upstream (see DATA.md). |
| Nabra-Saudi-82M (teacher) | https://huggingface.co/oddadmix/Nabra-Saudi-82M | Apache-2.0 | Distillation teacher for new voices | |
| Silero VAD | https://github.com/snakers4/silero-vad @ `v6.2.3` (file `src/silero_vad/data/silero_vad.onnx`, 2,327,524 bytes) | MIT (repo `LICENSE`, checked 2026-10-02) | Voice-activity detection for `listen`/`ask`/`inbox listen`, downloaded by `voxar models pull silero-vad` with pinned SHA-256 and run with `onnxruntime` (extra `vad`) | Used instead of the `silero-vad` pip package, which requires torch. |
| sherpa-onnx | https://github.com/k2-fsa/sherpa-onnx | Apache-2.0 | ONNX runtime and export recipes | License confirmed via GitHub API 2026-10-02. |

### Open license question: Moonshine Arabic model (checked 2026-10-02)

Evidence for MIT: Moonshine's repo `LICENSE` says every streaming model is MIT and lists only the legacy non-streaming Arabic Base/Tiny as non-commercial; the docs table lists "Arabic Tiny Streaming ... MIT"; the Hugging Face card for `moonshine-streaming-tiny-ar` is tagged MIT.

Evidence against / residual risk: `moonshine-voice` 0.1.5 prints "Using a model released under the non-commercial Moonshine Community License" for **every** non-English language (a hard-coded `language != "en"` check in `download.py`, not a per-model check). The CDN artifact we download (`quantized_26_08_24`, ONNX-runtime format) is not byte-identical to the Hugging Face repo (a Transformers checkpoint), so the MIT tag cannot be tied to it by hash.

Assessment: most likely MIT and the warning is stale, but this is not confirmed. **Get written confirmation from Moonshine AI before any commercial use or release.** `voxar models pull` shows this uncertainty in the license text it asks you to accept.

### Optional dependencies of the `moonshine` extra (checked 2026-10-02 via PyPI metadata)

| Package | License |
|---|---|
| moonshine-voice | MIT |
| numpy | BSD-3-Clause (and others, permissive) |
| sounddevice (needs the PortAudio library) | MIT |
| cffi / pycparser | MIT-0 / BSD-3-Clause |
| google-crc32c, requests | Apache-2.0 |
| tqdm | MPL-2.0 AND MIT (weak, file-level copyleft; fine as an unmodified dependency) |
| filelock, platformdirs | MIT |

### Optional extra `vad` (checked 2026-10-02 with `pip-licenses`)

| Package | License |
|---|---|
| onnxruntime | MIT |
| flatbuffers | Apache-2.0 |
| protobuf, sympy, mpmath | BSD |
| coloredlogs, humanfriendly | MIT |

### Optional extras `mcp` and `server` (checked 2026-10-02 with `pip-licenses` in a clean environment and `pip-audit`: no GPL, no unknown licenses, no known vulnerabilities)

`mcp` 2.2 (MIT) pulls pydantic, starlette, anyio, jsonschema, PyJWT/cryptography, httpx2, sse-starlette, uvicorn and others (MIT / BSD-3 / Apache-2.0, with `certifi` under MPL-2.0). `server` adds fastapi (MIT), uvicorn (BSD-3) and websockets (BSD-3). MPL-2.0 (`certifi`, `tqdm`) is weak, file-level copyleft and fine as an unmodified dependency.

CI audits core and core + all optional extras separately and fails on any license containing "GPL" or "UNKNOWN".

## Used only by the optional TTS plugin `voxar-tts-espeak` (GPL-3.0; never imported by the core)

Checked 2026-10-02 (PyPI metadata, GitHub API, `pip-licenses` and `pip-audit` on the installed plugin environment: no known vulnerabilities). See `docs/adr/0002-license-split.md`.

| Component | License | Why it is here |
|---|---|---|
| `espeak-ng` | GPL-3.0 | Arabic grapheme-to-phoneme used by Nabra-Saudi's `arabic_g2p.py` |
| `phonemizer-fork` | GPL-3.0+ | Python wrapper the misaki/Nabra phonemization path uses |
| `kokoro`, `misaki` | Apache-2.0 | TTS runtime and phoneme helpers (Nabra vendors a patched `kokoro_patched/`) |
| `camel-tools` | MIT | Not used (dialect text is synthesized without diacritization) |
| `torch` (BSD-style), `transformers`, `huggingface-hub` (Apache-2.0), `numpy` (BSD), `loguru` (MIT) | permissive | Neural network runtime for the vendored code |
| `espeakng-loader` | **metadata says UNKNOWN**; its GitHub repo says MIT | Wheel bundling the GPL-3.0 espeak-ng library and data. The missing wheel metadata is a packaging gap, not evidence of a different license; the bundled espeak-ng is GPL-3.0, which the plugin's GPL-3.0-only license covers |

Because the GPL components make a combined work GPL-3.0, the TTS plugin is its own GPL-3.0-only package (`plugins/voxar-tts-espeak`). It also vendors Apache-2.0 and MIT (StyleTTS2) code with notices in its `NOTICE` and `LICENSES/`.

## Deliberately NOT used

| Component | License | Reason |
|---|---|---|
| `moonshine-ai/moonshine-tiny-ar`, `moonshine-base-ar` (non-streaming) | Moonshine Community License (non-commercial) | Non-commercial. Only the streaming Arabic model is MIT. |
| Moonshine text-to-speech and grapheme-to-phoneme models/data | Own licenses, listed in `core/moonshine-tts/data/README.md` of the Moonshine repo | Not covered by Moonshine's MIT default. We use Nabra for TTS instead. |
| `NAMAA-Space/NAMAA-Saudi-TTS-V2` | CC-BY-NC-SA-4.0 | Non-commercial. |
| `VohoAI/voho-saudi-stt-small` | CC-BY-NC-SA-4.0 | Non-commercial. |

## Our own code

Apache-2.0, see `LICENSE`.
