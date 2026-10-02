# Language models (`voxar llm`)

voxar can send text to a language model, so a spoken conversation can be speech-to-text, then the model, then text-to-speech. This page covers the model step. Speech recognition and synthesis stay on your machine; only the **text** you choose to send goes to the provider.

```bash
export HUMAIN_NODE_API_KEY=...              # set it in your shell or secret manager, never in a file in the repo
uv run voxar llm models                     # the models your key can use
uv run voxar llm ask "مرحبا" --model MODEL_ID
```

## Providers

```bash
uv run voxar llm providers                  # names, where they run, and whether their key is set
```

| Provider | `--provider` | Key variable | Protocol |
|---|---|---|---|
| HUMAIN Node (default) | `humain` | `HUMAIN_NODE_API_KEY` | OpenAI Chat Completions |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` | OpenAI Chat Completions |
| OpenAI | `openai` | `OPENAI_API_KEY` | OpenAI Chat Completions |
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` | Anthropic Messages |
| Groq | `groq` | `GROQ_API_KEY` | OpenAI Chat Completions |
| Together AI | `together` | `TOGETHER_API_KEY` | OpenAI Chat Completions |
| Mistral | `mistral` | `MISTRAL_API_KEY` | OpenAI Chat Completions |
| Google Gemini | `gemini` | `GEMINI_API_KEY` | OpenAI Chat Completions |
| Ollama (on this machine) | `ollama` | none | OpenAI Chat Completions |
| LM Studio (on this machine) | `lmstudio` | none | OpenAI Chat Completions |
| Any other compatible server | `custom` | `VOXAR_LLM_API_KEY` | OpenAI Chat Completions |

Only HUMAIN Node has a default model (`humain-m3-preview`). For every other provider pass `--model`, or set `VOXAR_LLM_MODEL`; `voxar llm models --provider NAME` lists what your key can use. For `custom`, also pass `--base-url` (or set `VOXAR_LLM_BASE_URL`).

HUMAIN Node replies are fetched whole rather than streamed. Every other provider streams, so `voxar llm ask` prints text as it arrives; add `--no-stream` to print the finished reply instead.

## Configuration

| Variable | Meaning | Default |
|---|---|---|
| `VOXAR_LLM_PROVIDER` | Provider name from the table | `humain` |
| `VOXAR_LLM_MODEL` | Model id | the provider's default, if it has one |
| `VOXAR_LLM_BASE_URL` | Replace the provider's URL | the provider's URL |

Precedence: command-line flag, then these variables, then the provider's own default.

## Safety

- **Keys come from the environment only.** They are sent in a request header, never printed, and removed from any error message. Do not put one in a file that is committed or in a chat.
- **https only.** Plain `http` is accepted for `localhost`, `127.0.0.1` and `::1` and nowhere else.
- **No redirects.** A redirect would resend your key to another host, so any redirect is an error.
- **`VOXAR_OFFLINE=1` blocks remote providers.** Only `ollama`, `lmstudio` and loopback URLs still work.
- **What leaves your machine:** the prompt text you send. Remote providers have their own retention and privacy terms; a local provider keeps everything on the machine.
- Reasoning text some models return is never printed or spoken; an empty reply is an error, never silence.

## Errors

Each failure is one line that says what to do: `rejected the API key` names the variable to check, `could not find the model` points at `voxar llm models`, a rate limit shows the `Retry-After` wait, and a server error includes the provider's request id when it sends one.

## Python

```python
import os
from voxar import Config
from voxar.llm import Message, client_from_config

client = client_from_config(
    Config.from_env(os.environ), os.environ, provider="openrouter", model="MODEL_ID"
)
print(client.reply([Message("user", "مرحبا")], system="Answer in one short sentence."))
```

## What has been tested

The client is tested against a local fake server that imitates both wire protocols: request shape, headers, streaming, every error status, the https rule, and that a key never appears in an error. **No real provider has been called from this repository's tests**, so run `voxar llm models` with your own key before relying on one.
