# Agents (MCP)

`voxar mcp` runs a [Model Context Protocol](https://modelcontextprotocol.io) server over **stdio**, so an agent can transcribe audio and speak text.

```bash
uv sync --extra moonshine --extra mcp
uv run voxar mcp --allow-dir ./audio
```

Add it to an MCP client as a stdio server whose command is `voxar` with arguments `mcp --allow-dir /path/to/audio`.

## Tools

| Tool | Arguments | Result |
|---|---|---|
| `transcribe_file` | `path` (16 kHz mono 16-bit WAV) | the transcript |
| `speak` | `text`, `output_path`, optional `voice`, optional `overwrite` (default false) | where the WAV was written and its length |
| `list_engines` | none | installed recognizers and synthesizers |

`speak` needs a synthesizer: install the [plugin](text-to-speech.md) in the same environment and set `VOXAR_SYNTHESIZER=nabra-saudi`.

## Safety

An agent controls every argument, so:

- File paths must resolve **inside an allowed directory** (default: the working directory; repeat `--allow-dir` for more). `..` and symlinks cannot escape. Anything else is a tool error.
- `speak` **never overwrites** an existing file unless `overwrite=true`.
- Only WAV audio is read.
- stdout is the protocol channel; logs go to stderr.
- Errors are returned to the agent as readable tool errors (for example "no synthesizer configured").
