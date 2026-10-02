# Agents (MCP) and voice

`voxar mcp` runs a [Model Context Protocol](https://modelcontextprotocol.io) server over **stdio**. Any MCP client can launch it, for example Claude Code or Codex. It has two parts:

- **File tools** (always on): transcribe a WAV file, write speech to a WAV file, list engines.
- **Voice tools** (opt-in, `--voice`): the agent can say a short status update out loud, ask you a question and hear your answer, using this machine's speakers and microphone. Speech recognition and synthesis run locally; only the text reaches the agent. The agent speaks with the Saudi-dialect voice, and the server tells it to write the way a Saudi speaker talks.
- **Voice inbox** (with `--voice`): you can speak to a *running* agent from a second window, for example to give it a task, and it picks the message up. See [Talk to a running agent](#talk-to-a-running-agent-from-another-window).

```bash
uv sync --extra moonshine --extra mcp
uv run voxar models pull moonshine-tiny-streaming-ar --accept-license
uv run voxar mcp --allow-dir ./audio            # file tools only
uv run voxar mcp --voice                        # file tools and voice tools
```

Speaking needs a synthesizer: install the [text-to-speech plugin](text-to-speech.md) in the same environment and set `VOXAR_SYNTHESIZER=nabra-saudi`. The Saudi voice speaks **Arabic**: Latin-script words and symbols are dropped, so spoken messages must be written in Arabic.

## Tools

| Tool | Arguments | Result |
|---|---|---|
| `transcribe_file` | `path` (16 kHz mono 16-bit WAV) | the transcript |
| `speak` | `text`, `output_path`, optional `voice`, optional `overwrite` (default false) | where the WAV was written and its length |
| `list_engines` | none | installed recognizers and synthesizers |
| `announce` *(voice)* | `message` (up to 500 characters), optional `voice` | speaks it on the speakers; returns when finished |
| `listen` *(voice)* | `max_seconds` (1 to 60, default 15), `silence_seconds` (0.5 to 5, default 1.5) | what the user said, or `(no speech heard)` |
| `ask` *(voice)* | `question`, plus the `listen` arguments and `voice` | speaks the question, then returns the spoken answer |
| `check_voice_inbox` *(voice)* | optional `wait_seconds` (0 to 60) | the spoken messages you sent from the listener window since the last check, each delivered once |

Recording starts at the first speech and ends after the silence gap or at `max_seconds`. Nothing is kept except the transcript text. Calls run one at a time, so an update never talks over a question.

The server also sends the agent short instructions: keep announcements to one or two plain sentences in Arabic, use `ask` only for a decision, and repeat back anything important because recognition can make mistakes.

## Talk to a running agent from another window

MCP only works when the agent asks, so it cannot hear you unprompted. To give an agent tasks by voice while you work in another window, run the listener there. It writes what you say into a small inbox that the agent reads.

```bash
uv run voxar inbox listen                # press Enter, speak, and see "heard: ..."
```

Everything must use the same `VOXAR_CACHE_DIR` (the default is fine if you set nothing), because the inbox is a file in that directory.

How the agent receives it:

- **Any MCP client (Claude Code, Codex):** the agent calls `check_voice_inbox` when it finishes a step. The server's instructions tell it to, and you can add the same sentence to `CLAUDE.md` or `AGENTS.md`. Messages arrive between steps, not in the middle of one.
- **Claude Code, even after it has stopped:** add a `Stop` hook that feeds the message in, so a spoken task restarts the agent without you touching its window. In `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run --directory /path/to/Voxar voxar inbox read --hook"
          }
        ]
      }
    ]
  }
}
```

`voxar inbox read --hook` prints nothing when there is no message. When there is one, it prints a decision that keeps Claude Code going with your words as the next instruction, and marks the message read. Plain `voxar inbox read` prints the messages, and `voxar inbox clear` deletes them.

Listening choices:

| Mode | Behavior |
|---|---|
| default | Waits for you to press Enter, records one phrase (until you pause), stores it. Nothing is recorded unless you ask. |
| `--wake WORD` | Keeps only phrases that contain the word, and removes it from the message. |
| `--always-on` | Listens continuously. **Anything the microphone hears becomes an instruction for your agent**, including other people and audio from videos. Use it only with `--wake`, in a quiet place, with an agent whose tool calls need your approval. |

## Use it with Claude Code

Register the server once (adjust the path to where you cloned voxar):

```bash
claude mcp add voxar -e VOXAR_SYNTHESIZER=nabra-saudi -- uv run --directory /path/to/Voxar voxar mcp --voice
```

Then ask Claude Code to use it, or put this in your project's `CLAUDE.md`:

```markdown
Keep me informed by voice with the voxar tools. When you finish a step, hit a problem or need
a decision, call announce with one or two plain sentences in simple Saudi Arabic (no code, no
file paths). Use ask only when you cannot continue without my answer, and repeat my answer back
before acting on it. When you finish a step, call check_voice_inbox: anything it returns is an
instruction from me.
```

To hear status **without the agent having to remember**, add a hook that speaks when Claude Code finishes a turn. In `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run --directory /path/to/Voxar voxar say 'خلصت من المهمة'"
          }
        ]
      }
    ]
  }
}
```

`voxar say TEXT` without `-o` plays the speech on the speakers. Set `VOXAR_SYNTHESIZER=nabra-saudi` in the environment the hook runs in.

## Use it with Codex

Add the server to `~/.codex/config.toml`:

```toml
[mcp_servers.voxar]
command = "uv"
args = ["run", "--directory", "/path/to/Voxar", "voxar", "mcp", "--voice"]
env = { VOXAR_SYNTHESIZER = "nabra-saudi" }
```

and put the same instruction paragraph in your project's `AGENTS.md`. Codex uses the MCP tools, including `check_voice_inbox`; the `Stop` hook above is Claude Code only.

> These steps follow each client's documented configuration but have **not been run against Claude Code or Codex from this repository**; the server itself is tested with the official MCP Python client and fake audio devices, and the real microphone and speakers are untested. If a client changes its configuration format, check its own documentation.

## Safety

An agent controls every argument, so:

- File paths must resolve **inside an allowed directory** (default: the working directory; repeat `--allow-dir` for more). `..` and symlinks cannot escape. Anything else is a tool error.
- `speak` **never overwrites** an existing file unless `overwrite=true`.
- Only WAV audio is read.
- **The microphone and speakers are off unless you pass `--voice`.** Without it the voice tools do not exist.
- With `--voice`, the microphone is open only while a `listen` or `ask` call runs, for at most 60 seconds, and only the transcript is returned. Your client's tool-approval prompts are the control over when that happens; do not auto-approve `listen` and `ask` if you do not want an agent able to hear you at any time.
- Spoken text is limited to 500 characters.
- **Anything transcribed becomes an instruction.** The inbox sends your speech to an agent that may run commands. That is why the default is push-to-talk, why `--always-on` warns and works best with `--wake`, and why every message reaches the agent labeled as automatically transcribed, with a reminder to confirm risky actions out loud. Keep your client's approval prompts on for risky tools.
- stdout is the protocol channel; logs go to stderr.
- Errors are returned to the agent as readable tool errors (for example "no synthesizer configured").
