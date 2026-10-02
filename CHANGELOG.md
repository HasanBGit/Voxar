# Changelog

## 0.0.1 (unreleased)

- Core library: domain types and one error hierarchy, `SpeechRecognizer` and `SpeechSynthesizer` ports, lazy engine registry (explicit and entry points), `Config` from environment variables, model store with pinned SHA-256 and atomic verified install, WAV handling and chunking, the `Voxar` facade.
- Command line: `voxar transcribe`, `listen` (microphone), `say`, `models list|pull|verify`, `mcp`, `serve`, `doctor`.
- Moonshine streaming Arabic speech-to-text engine (`voxar[moonshine]`).
- Saudi text-to-speech plugin `plugins/voxar-tts-espeak` (GPL-3.0-only, separate project): `nabra-saudi` synthesizer, voice `af_msa`, 24 kHz.
- `voxar mcp`: MCP server over stdio (`voxar[mcp]`) with tools `transcribe_file`, `speak` and `list_engines`. File paths are confined to `--allow-dir`, and `speak` does not overwrite unless asked.
- `voxar serve`: local FastAPI server (`voxar[server]`) with `POST /v1/transcribe`, `POST /v1/speak` and live `WS /v1/stream`. Loopback-only unless `--allow-remote`; Host/Origin guard against DNS rebinding; upload, stream and concurrency limits (one job per engine at a time, a queue of 8, then `503` with `Retry-After`; 4 live streams, then close code 1013). Engines load in the background at start-up (`--no-warm` to opt out).
- Browser test page at `/` (`voxar/ui/index.html`, single file, no build step): drop or stream audio to transcribe, type text to hear the Saudi voice, copy and download buttons, dark mode, phone layout.
- Long audio is transcribed in 2 s chunks (100 ms chunks up to 15 s); an explicit `chunk_ms` always wins.
- Eight example scripts in `examples/`.
- Benchmark and load-test scripts (`scripts/benchmark.py`, `scripts/loadtest.py`); results in `docs/performance.md`.
- `Makefile` with `make setup`, `make models`, `make run`, `make test`, `make check`.
- CI: lint, type check and tests on Linux, macOS and Windows; runtime-dependency license audit (fails on GPL, AGPL or unknown); security scan; CodeQL; Dependabot.
- Documentation: README (English and Arabic), architecture, decision records, threat model, third-party license and data tracking.
