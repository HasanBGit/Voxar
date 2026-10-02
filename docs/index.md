# voxar

Dialect-aware speech for devices that cannot afford a GPU: streaming speech-to-text and small text-to-speech, running on-device, installable with one command. Saudi Arabic is the first supported dialect; the layout leaves room for more.

> **Pre-alpha.** Speed, memory and server load were measured on one machine: see [Performance](performance.md).

## What works today

| Capability | How | Notes |
|---|---|---|
| Arabic speech-to-text from a WAV file | `voxar transcribe` | Moonshine streaming Arabic (extra `voxar[moonshine]`) |
| Saudi-dialect text-to-speech | `voxar say` | Optional **GPL-3.0** plugin, needs torch; one female voice |
| Agent access | `voxar mcp` | MCP over stdio; file access confined to allowed directories |
| App access | `voxar serve` | Local HTTP/WebSocket and a browser test page; **no authentication**: keep it on localhost |
| Model download | `voxar models pull` | HTTPS only, every file checked against a pinned SHA-256 |

Also included: a browser test page served by `voxar serve` ([Local server](local-server.md)).

## Where to go next

- [Quickstart](quickstart.md): install, download the model, transcribe.
- [Command line](cli.md), [Python API](python-api.md), [Agents (MCP)](agents-mcp.md), [Local server](local-server.md).
- [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md): read this before any commercial use. One model's license is unconfirmed.
- [Architecture](../ARCHITECTURE.md), [threat model](THREAT_MODEL.md), [examples](../examples/README.md), [changelog](../CHANGELOG.md).
