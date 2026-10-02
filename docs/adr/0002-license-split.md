# ADR 0002: Split the GPL-dependent TTS path into a separate package

Status: accepted and implemented (2026-10-02): `plugins/voxar-tts-espeak` exists, is GPL-3.0-only, and core never imports it

## Context
The project policy is to follow each upstream license and not relicense third-party work. Checked on 2026-10-02:
- Moonshine streaming Arabic ASR, `moonshine-voice`, onnxruntime: MIT. numpy, soundfile: BSD. These are fine under Apache-2.0.
- The Nabra-Saudi TTS Arabic phonemizer calls `espeak-ng` through misaki and `phonemizer-fork`. `espeak-ng` and `phonemizer-fork` are GPL-3.0.

Importing GPL-3.0 code into an Apache-2.0 package would make the combined work subject to GPL-3.0.

## Decision
- `voxar` (core, ASR, CLI, MCP): Apache-2.0, runtime dependencies must not be GPL/AGPL. A CI job enforces this.
- `voxar-tts-espeak` (optional plugin that carries the TTS path): GPL-3.0, separate package and folder, loaded only through the engine registry when installed. Core never imports it.
- Long-term: replace espeak-based phonemization with a permissively licensed Saudi grapheme-to-phoneme step so TTS can join the Apache-2.0 core.

## Consequences
- Users who only need ASR get a clean Apache-2.0 install.
- TTS users accept GPL-3.0 for that plugin.
- This is an engineering decision, not legal advice. Ask a lawyer before commercial release.
