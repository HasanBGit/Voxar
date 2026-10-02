# Text-to-speech plugin

Speech synthesis lives in a **separate package, `voxar-tts-espeak`, licensed GPL-3.0-only**. It is separate on purpose: its runtime needs `espeak-ng` and `phonemizer-fork`, which are GPL-3.0, so the combined work is GPL-3.0. The voxar core stays Apache-2.0 and never imports it ([ADR 0002](adr/0002-license-split.md)). This is not legal advice.

It provides one synthesizer, `nabra-saudi`: Saudi-dialect Arabic, a single female voice (`af_msa`), 24 kHz mono, built on the Nabra-Saudi-7M model.

> **Heavy install.** It needs torch and transformers (a venv of roughly 900 MB). It is a desktop/server path. The route to low-end devices is a planned ONNX export that does not exist yet.

```bash
uv pip install -e plugins/voxar-tts-espeak
uv run voxar models pull nabra-saudi-7m --accept-license      # about 31 MB
VOXAR_SYNTHESIZER=nabra-saudi uv run voxar say "السلام عليكم" -o hello.wav
```

## Notes

- Write dialect text as people write it, **without full diacritics**; diacritics make this model worse.
- Latin-script words are dropped. Text with nothing speakable is an error, not silence.
- Long text is split into sentences and into chunks the model accepts; a single word that is too long is an error.
- Whether the voice's speaker consented to commercial use is not documented upstream. Check before commercial use ([licenses](../THIRD_PARTY_LICENSES.md)).
- The vendored model code was reviewed and has its network fallbacks removed; see `plugins/voxar-tts-espeak/src/voxar_tts_espeak/_vendor/UPSTREAM.md`.
