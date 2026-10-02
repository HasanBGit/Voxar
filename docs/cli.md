# Command line

```text
voxar [-h] [--version] {transcribe,listen,say,models,mcp,serve,llm,doctor} ...
```

Errors are printed as `error: <message>` with exit code 2 and never as a traceback. Messages say how to fix the problem.

| Command | What it does |
|---|---|
| `voxar transcribe FILE` | Transcribe a 16 kHz mono 16-bit WAV file and print the final text. |
| `voxar listen` | Transcribe the microphone live. Partial text updates in place on a terminal; Ctrl-C stops cleanly. |
| `voxar say TEXT -o OUT.wav [--voice NAME]` | Synthesize speech to a WAV file. Needs a synthesizer (see [Text-to-speech plugin](text-to-speech.md)). |
| `voxar models list` | List models voxar knows how to install. |
| `voxar models pull NAME --accept-license` | Download a model over HTTPS and verify every file's SHA-256. Safe to repeat. |
| `voxar models verify NAME` | Re-check an installed model's checksums. |
| `voxar mcp [--allow-dir DIR]...` | Run the MCP server on stdio. See [Agents (MCP)](agents-mcp.md). |
| `voxar serve [--host H] [--port P] [--allow-remote]` | Run the local HTTP/WebSocket server. See [Local server](local-server.md). |
| `voxar llm providers` | List language-model providers and whether each key is set. See [Language models](llm.md). |
| `voxar llm models [--provider P]` | List the models your key can use. |
| `voxar llm ask TEXT [--provider P] [--model M] [--system S] [--no-stream]` | Send one message and print the reply. |
| `voxar doctor` | Show versions, cache directory and installed engines. |

## Models

| Name | What | Size | License |
|---|---|---|---|
| `moonshine-tiny-streaming-ar` | Arabic streaming speech-to-text | about 31 MB | MIT per upstream, unconfirmed for the downloaded file |
| `nabra-saudi-7m` | Saudi-dialect text-to-speech (single voice) | about 31 MB | Apache-2.0 (weights); the engine that runs it is GPL-3.0 |
