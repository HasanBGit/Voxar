# Local server

`voxar serve` runs a small HTTP/WebSocket server for a browser or phone app on the same machine.

```bash
uv sync --extra moonshine --extra server
uv run voxar serve            # http://127.0.0.1:8765
```

> **No authentication.** The server has **no authentication and no HTTPS**. It binds to `127.0.0.1` and refuses any other address unless you pass `--allow-remote` (which also turns off the Host/Origin checks). Do not expose it to a network you do not trust.

## Test page

Open the server's address (default `http://127.0.0.1:8765`) in a browser for a small test page: record or upload audio to get a transcript, type text to hear the Saudi voice, with the status of both engines in the header. It is one self-contained file (`voxar/ui/index.html`, no build step) and loads no scripts from the network; only its fonts come from public CDNs, with system fallbacks. Its **Listen** panel streams the microphone to `WS /v1/stream` and shows partial text as you speak (Space starts and stops, a level meter shows the microphone is heard), or transcribes a dropped audio file at once; its **Speak** panel speaks typed text or one of three sample sentences. See the screenshots in the README.

## Endpoints

| Method and path | Body | Response |
|---|---|---|
| `GET /` | none | the test page (HTML) |
| `GET /health` | none | `{"status": "ok", "version": ..., "recognizers": [...], "synthesizers": [...]}` |
| `POST /v1/transcribe` | raw 16 kHz mono 16-bit WAV bytes | `{"text": "..."}` |
| `POST /v1/speak` | JSON `{"text": "...", "voice": null}` | `audio/wav` bytes |
| `WS /v1/stream` | binary frames of 16 kHz mono 16-bit PCM; a text frame (any) ends the stream | JSON messages `{"text": "...", "final": false/true}` or `{"error": "..."}` |

Errors are JSON `{"error": "..."}`: 400 for bad input, 413 for an oversized upload, 503 when an engine or model is missing (the message says how to fix it).

```bash
curl -X POST --data-binary @sample.wav http://127.0.0.1:8765/v1/transcribe
```

## Protections

- **DNS rebinding:** requests whose `Host` is not a loopback name get 403; WebSocket upgrades with a foreign `Origin` or `Host` are closed with code 1008.
- **Limits:** uploads up to 50 MB and streams up to one hour. Each engine runs one job at a time (measured: concurrent jobs on one model are slower in total); up to 8 more requests wait, and further ones get `503` with `Retry-After: 1` at once, so clients should back off and retry (see `examples/04_http_client.py`). Up to four live streams run at once; a fifth gets `{"error": ...}` and is closed with code 1013 (try again later).
- The recognizer model is loaded once and shared by all requests and streams. Engines load in the background when the server starts, so the first request is fast (first Speak 0.14 to 0.20 s instead of about 3.0 s when loaded on first use, measured over 3 fresh starts); `voxar serve --no-warm` loads them on first use instead, which saves about 270 MB of memory until then.

The server has no authentication, HTTPS or per-client limits.
