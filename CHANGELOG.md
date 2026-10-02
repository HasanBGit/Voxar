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
- `voxar llm` and `voxar.llm`: chat clients for HUMAIN Node (default), OpenRouter, OpenAI, Anthropic, Groq, Together, Mistral, Gemini, Ollama, LM Studio and any OpenAI-compatible server; `providers`, `models` and `ask` commands; settings `VOXAR_LLM_PROVIDER`, `VOXAR_LLM_MODEL`, `VOXAR_LLM_BASE_URL`. Keys come from environment variables only, https is required except for loopback, redirects are refused, and `VOXAR_OFFLINE=1` blocks remote providers. Tested against a local fake server only.
- MCP voice tools (`voxar mcp --voice`): `announce`, `listen` and `ask` let an agent such as Claude Code or Codex speak a short status update, or hear and transcribe what you say, through this machine's speakers and microphone. Off unless `--voice` is given. `voxar say` without `-o` now plays on the speakers, which works as a hook. Tool descriptions, annotations and server instructions were rewritten so agents use the tools well. Tested with fake audio devices; the real microphone, speakers, Claude Code and Codex are untested.
- Voice inbox: `voxar inbox listen` (a second window; press Enter, or `--always-on` with `--wake WORD`) turns what you say into messages for a running agent. Agents read them with the new `check_voice_inbox` MCP tool (Claude Code and Codex), and `voxar inbox read --hook` feeds them to a Claude Code `Stop` hook. The server now tells agents to write spoken text in simple Saudi Arabic. Verified across separate processes with the real stdio server; microphone, Claude Code and Codex untested.
- Eight example scripts in `examples/`.
- Benchmark and load-test scripts (`scripts/benchmark.py`, `scripts/loadtest.py`); results in `docs/performance.md`.
- `Makefile` with `make setup`, `make models`, `make run`, `make test`, `make check`.
- CI: lint, type check and tests on Linux, macOS and Windows; runtime-dependency license audit (fails on GPL, AGPL or unknown); security scan; CodeQL; Dependabot.
- Documentation: README (English and Arabic), architecture, decision records, threat model, third-party license and data tracking.
