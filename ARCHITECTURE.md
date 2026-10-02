# Architecture

Status: the core, the Moonshine ASR engine, model download, and microphone input exist and are tested. The Saudi TTS plugin (`plugins/voxar-tts-espeak`, GPL-3.0, separate project) exists. The MCP server (`voxar.mcp_server`) and the optional local HTTP/WebSocket server (`voxar.server`) exist; both only call the facade. *(planned)* marks what is missing.

## Goal

On-device, dialect-aware speech: streaming speech-to-text (STT) and text-to-speech (TTS), usable from Python, a CLI, an MCP server and an optional local server. Everything runs locally; audio never leaves the machine.

## Shape: ports and adapters

The core defines *what* we need (small interfaces). Engines implement them. Nothing in the core imports a third-party speech library.

```
          CLI / MCP server / optional HTTP+WebSocket server
                              |
                          voxar.api            (facade: transcribe, stream, speak)
                              |
         +--------------------+--------------------+
         |                    |                    |
   voxar.registry       voxar.models          voxar.audio
 (find engines by    (cache, pinned         (file/mic sources,
   entry point)      revision + SHA-256)     resample to 16 kHz mono)
         |
   voxar.ports  (typing.Protocol: SpeechRecognizer, SpeechSynthesizer, ...)
         ^
         | implemented by
   voxar.engines.*  (adapters; third-party imports are lazy)
```

Dependencies point inwards: adapters depend on ports, never the reverse.

## Modules

| Module | Responsibility | Must not |
|---|---|---|
| `voxar.domain` | Immutable data types and the error hierarchy | do I/O or import adapters |
| `voxar.ports` | `Protocol` interfaces | contain logic |
| `voxar.config` | One frozen `Config` (env `VOXAR_*`, then arguments) | read config from anywhere else |
| `voxar.models` | Model catalog (name, revision, SHA-256, license), cache, offline mode, safe loading | load untrusted pickles |
| `voxar.audio` | WAV read/write and chunking (standard library only). Resampling is *(planned)* behind an optional extra | know about engines |
| `voxar.engines.*` | One adapter per engine. Exists: `moonshine` (ASR). The TTS adapter lives in the separate GPL-3.0 plugin `plugins/voxar-tts-espeak`, registered through the `voxar.synthesizers` entry point | leak third-party types outward |
| `voxar.net` | HTTPS-only streaming download for model files; the only module that uses the network | be imported by anything except the CLI |
| `voxar.mic` | Microphone source (16 kHz mono int16 blocks) via `sounddevice`, bounded queue, Ctrl-C ends the stream cleanly | know about engines |
| `voxar.registry` | Look up engines through entry points `voxar.recognizers` / `voxar.synthesizers` | import engines eagerly |
| `voxar.api` | Small public facade | hold global state |
| `voxar.mcp_server` | MCP tools for agents; confines file paths to allowed directories; turns our errors into tool errors | print to stdout (it is the protocol channel) |
| `voxar.server` | Optional FastAPI app: transcribe, speak, live WebSocket; Host/Origin guard, size and length limits | be imported by the core or by anything except the CLI |
| `voxar.testing` | Shared engine contract checks that adapters and plugins reuse in their own tests | be imported by production code |
| `voxar.cli` | `argparse` command line | contain business logic |

The public API is only what `voxar/__init__.py` exports. Everything else is internal.

## Licensing boundary

The core and the speech-recognition engine are Apache-2.0 with MIT/BSD dependencies. The TTS path used by Nabra needs `espeak-ng` and `phonemizer-fork` (GPL-3.0), so TTS ships as a **separate optional package** that core never imports. See `docs/adr/0002-license-split.md`. CI fails if the core's runtime dependencies contain GPL/AGPL.

## Error handling

Validate at the boundary and fail fast with typed errors that say how to fix the problem (`InvalidAudioError`: the ffmpeg command that converts the file; `EngineUnavailableError`: what is available and how to install an engine; `ModelNotFoundError`: how to install the model, `voxar models pull NAME --accept-license`). Cheap input checks run before an engine is created. The same error and the same message appear from the CLI, the API and the MCP server.

## Testing

Unit tests use fakes for every port (no network, no models). One reusable contract-test suite runs against every engine adapter. A few opt-in integration tests (`-m integration`) use real tiny models. See `CONTRIBUTING.md`.

## Decisions

Recorded in `docs/adr/`. Threat model: `docs/THREAT_MODEL.md`.
