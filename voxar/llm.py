"""Chat clients for the language model behind a voice conversation.

Two wire protocols cover every provider voxar supports: the OpenAI Chat Completions API (HUMAIN
Node, OpenRouter, OpenAI, Groq, Together, Mistral, Gemini, Ollama, LM Studio, any compatible
server) and the Anthropic Messages API. Standard library only, so the core keeps no runtime
dependencies. Remote providers must use https; plain http is accepted for loopback addresses only.
API keys are read from the environment, sent only in a request header, and never put in a message.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from http.client import HTTPMessage
from typing import IO, Any, Literal

from voxar import __version__
from voxar.config import Config
from voxar.domain import ConfigError, LLMError, OfflineModeError

DEFAULT_PROVIDER = "humain"
DEFAULT_MAX_TOKENS = 400  # spoken answers are short
ANTHROPIC_VERSION = "2023-06-01"
_TIMEOUT_S = 60.0
_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
_REASON_LIMIT = 300

Role = Literal["user", "assistant"]
Protocol = Literal["openai", "anthropic"]


@dataclass(frozen=True)
class Message:
    """One turn of a conversation. The system prompt is passed separately."""

    role: Role
    content: str

    def __post_init__(self) -> None:
        if self.role not in ("user", "assistant"):
            raise ValueError(f"role must be 'user' or 'assistant', got {self.role!r}")
        if not self.content.strip():
            raise ValueError("message content must not be empty")


@dataclass(frozen=True)
class Provider:
    name: str
    label: str
    protocol: Protocol
    base_url: str | None
    key_env: str | None
    default_model: str | None = None
    local: bool = False  # runs on this machine: no key needed, nothing leaves the device
    streaming: bool = True


def _openai(
    name: str, label: str, base_url: str | None, key_env: str | None, **kw: Any
) -> Provider:
    return Provider(name, label, "openai", base_url, key_env, **kw)


PROVIDERS: dict[str, Provider] = {
    p.name: p
    for p in (
        # HUMAIN Node is the primary provider. Its gateway answers "Streaming is not supported" for
        # the preview model, so replies are fetched whole.
        _openai(
            "humain",
            "HUMAIN Node",
            "https://api.node.humain.com/v1",
            "HUMAIN_NODE_API_KEY",
            default_model="humain-m3-preview",
            streaming=False,
        ),
        _openai("openrouter", "OpenRouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
        _openai("openai", "OpenAI", "https://api.openai.com/v1", "OPENAI_API_KEY"),
        Provider(
            "anthropic",
            "Anthropic",
            "anthropic",
            "https://api.anthropic.com/v1",
            "ANTHROPIC_API_KEY",
        ),
        _openai("groq", "Groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY"),
        _openai("together", "Together AI", "https://api.together.xyz/v1", "TOGETHER_API_KEY"),
        _openai("mistral", "Mistral", "https://api.mistral.ai/v1", "MISTRAL_API_KEY"),
        _openai(
            "gemini",
            "Google Gemini",
            "https://generativelanguage.googleapis.com/v1beta/openai",
            "GEMINI_API_KEY",
        ),
        _openai("ollama", "Ollama", "http://localhost:11434/v1", None, local=True),
        _openai("lmstudio", "LM Studio", "http://localhost:1234/v1", None, local=True),
        # Any other OpenAI-compatible server: pass --base-url (or VOXAR_LLM_BASE_URL).
        _openai("custom", "the custom endpoint", None, "VOXAR_LLM_API_KEY"),
    )
}


def provider_named(name: str) -> Provider:
    try:
        return PROVIDERS[name]
    except KeyError:
        raise ConfigError(
            f"unknown LLM provider {name!r}; choose one of: {', '.join(PROVIDERS)}"
        ) from None


def _is_loopback(url: str) -> bool:
    return urllib.parse.urlsplit(url).hostname in _LOOPBACK


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """A redirect would resend the Authorization header to another host: refuse every one."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        raise LLMError(
            "the provider answered with a redirect; check the base URL (it must be final)"
        )


class ChatClient:
    """Talk to one provider. ``reply`` returns the whole answer, ``stream`` yields text pieces."""

    def __init__(
        self,
        provider: Provider,
        *,
        model: str | None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = _TIMEOUT_S,
    ) -> None:
        url = (base_url or provider.base_url or "").rstrip("/")
        if not url:
            raise ConfigError(
                f"{provider.label} needs a base URL: pass --base-url or set VOXAR_LLM_BASE_URL"
            )
        if not url.startswith("https://") and not (url.startswith("http://") and _is_loopback(url)):
            raise ConfigError(
                f"LLM base URL must use https (http is allowed only for localhost), got {url!r}"
            )
        if api_key is None and not provider.local and not _is_loopback(url):
            raise ConfigError(
                f"{provider.label} needs an API key: set {provider.key_env or 'VOXAR_LLM_API_KEY'}"
            )
        self._provider = provider
        self._model = model
        self._url = url
        self._key = api_key
        self._timeout = timeout

    @property
    def provider(self) -> Provider:
        return self._provider

    @property
    def model(self) -> str | None:
        return self._model

    def reply(
        self,
        messages: Sequence[Message],
        *,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> str:
        body = self._chat_body(messages, system, max_tokens, stream=False)
        data = self._json("POST", self._chat_path(), body)
        try:
            text = _anthropic_text(data) if self._anthropic else _openai_text(data)
        except (KeyError, IndexError, TypeError, AttributeError):
            raise LLMError(f"unexpected response from {self._provider.label}") from None
        if not text.strip():
            raise LLMError(f"{self._provider.label} returned an empty reply; try again")
        return text

    def stream(
        self,
        messages: Sequence[Message],
        *,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Iterator[str]:
        if not self._provider.streaming:
            yield self.reply(messages, system=system, max_tokens=max_tokens)
            return
        body = self._chat_body(messages, system, max_tokens, stream=True)
        spoke = False
        for line in self._lines("POST", self._chat_path(), body):
            piece = self._stream_piece(line)
            if piece:
                spoke = True
                yield piece
        if not spoke:
            raise LLMError(f"{self._provider.label} returned an empty reply; try again")

    def models(self) -> list[str]:
        data = self._json("GET", "/models", None)
        try:
            return sorted(str(item["id"]) for item in data["data"])
        except (KeyError, TypeError):
            raise LLMError(f"unexpected response from {self._provider.label}") from None

    @property
    def _anthropic(self) -> bool:
        return self._provider.protocol == "anthropic"

    def _chat_path(self) -> str:
        return "/messages" if self._anthropic else "/chat/completions"

    def _chat_body(
        self, messages: Sequence[Message], system: str | None, max_tokens: int, *, stream: bool
    ) -> dict[str, Any]:
        if not self._model:
            raise ConfigError("an LLM model name is required: pass --model or set VOXAR_LLM_MODEL")
        turns = [{"role": m.role, "content": m.content} for m in messages]
        body: dict[str, Any] = {"model": self._model, "max_tokens": max_tokens}
        if self._anthropic:
            body["messages"] = turns
            if system:
                body["system"] = system
        else:
            body["messages"] = ([{"role": "system", "content": system}] if system else []) + turns
        if stream:
            body["stream"] = True
        return body

    def _stream_piece(self, line: bytes) -> str:
        text = line.decode("utf-8", errors="replace").strip()
        if not text.startswith("data:"):
            return ""
        payload = text[5:].strip()
        if not payload or payload == "[DONE]":
            return ""
        try:
            event = json.loads(payload)
            if self._anthropic:
                delta = event.get("delta") or {}
                return (
                    str(delta.get("text") or "")
                    if event.get("type") == "content_block_delta"
                    else ""
                )
            return str(event["choices"][0]["delta"].get("content") or "")
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            return ""

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None
    ) -> urllib.request.Request:
        headers = {"User-Agent": f"voxar/{__version__}", "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self._key:
            if self._anthropic:
                headers["x-api-key"] = self._key
            else:
                headers["Authorization"] = f"Bearer {self._key}"
        if self._anthropic:
            headers["anthropic-version"] = ANTHROPIC_VERSION
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        # the scheme was checked in __init__ (https, or http for loopback), so S310 cannot apply
        return urllib.request.Request(  # noqa: S310
            self._url + path, data=payload, headers=headers, method=method
        )

    def _open(self, method: str, path: str, body: dict[str, Any] | None) -> Any:
        request = self._request(method, path, body)
        opener = urllib.request.build_opener(_NoRedirects)
        try:
            return opener.open(request, timeout=self._timeout)
        except urllib.error.HTTPError as exc:
            raise self._http_error(exc) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LLMError(
                f"could not reach {self._provider.label} at {self._url}: "
                f"{_scrub(str(exc), self._key)}. "
                f"{_reach_hint(self._provider)}"
            ) from None

    def _json(self, method: str, path: str, body: dict[str, Any] | None) -> Any:
        with self._open(method, path, body) as response:
            raw = response.read()
        try:
            return json.loads(raw)
        except ValueError:
            raise LLMError(f"unexpected response from {self._provider.label}") from None

    def _lines(self, method: str, path: str, body: dict[str, Any] | None) -> Iterator[bytes]:
        with self._open(method, path, body) as response:
            yield from response

    def _http_error(self, exc: urllib.error.HTTPError) -> LLMError:
        label, status = self._provider.label, exc.code
        reason = _reason(exc, self._key)
        request_id = exc.headers.get("X-Request-ID") if exc.headers else None
        suffix = f" (request id {request_id})" if request_id else ""
        if status == 401:
            key_env = self._provider.key_env or "the API key"
            message = f"{label} rejected the API key (HTTP 401); check {key_env}"
        elif status == 403:
            message = f"{label} denied the request (HTTP 403): {reason}"
        elif status == 404:
            message = (
                f"{label} could not find the model or endpoint (HTTP 404): {reason}. "
                "List what this key can use with: "
                f"voxar llm models --provider {self._provider.name}"
            )
        elif status == 429:
            wait = exc.headers.get("Retry-After") if exc.headers else None
            when = f"retry after {wait}s" if wait else "retry in a moment"
            message = f"{label} rate limit or quota reached (HTTP 429); {when}"
        elif status >= 500:
            message = f"{label} is unavailable (HTTP {status}); try again later"
        elif status == 400:
            message = f"{label} rejected the request (HTTP 400): {reason}"
        else:
            message = f"{label} returned HTTP {status}: {reason}"
        return LLMError(message + suffix)


def client_from_config(
    config: Config,
    env: Mapping[str, str],
    *,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    need_model: bool = True,
) -> ChatClient:
    """Build a client from explicit values, then ``VOXAR_LLM_*``, then the provider's defaults."""
    chosen = provider_named(provider or config.llm_provider or DEFAULT_PROVIDER)
    url = base_url or config.llm_base_url or chosen.base_url
    if config.offline and not (chosen.local or (url and _is_loopback(url))):
        raise OfflineModeError(
            f"VOXAR_OFFLINE is set, so {chosen.label} cannot be used; "
            "use a local provider (--provider ollama or lmstudio) or unset it"
        )
    name = model or config.llm_model or chosen.default_model
    if not name and need_model:
        raise ConfigError(
            f"{chosen.label} has no default model: pass --model or set VOXAR_LLM_MODEL "
            f"(list them with: voxar llm models --provider {chosen.name})"
        )
    key = env.get(chosen.key_env) if chosen.key_env else None
    return ChatClient(chosen, model=name or None, base_url=url, api_key=key or None)


def _openai_text(data: Any) -> str:
    content = data["choices"][0]["message"]["content"]
    if isinstance(content, list):  # some gateways return typed parts; reasoning parts are skipped
        return "".join(p.get("text", "") for p in content if p.get("type") == "text")
    return "" if content is None else str(content)


def _anthropic_text(data: Any) -> str:
    return "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")


def _scrub(text: str, key: str | None) -> str:
    return text.replace(key, "***") if key else text


def _reason(exc: urllib.error.HTTPError, key: str | None) -> str:
    """The provider's own explanation, short, and never containing the API key."""
    try:
        data = json.loads(exc.read())
        error = data.get("error", data) if isinstance(data, dict) else data
        text = error.get("message") if isinstance(error, dict) else str(error)
    except (ValueError, AttributeError, OSError):
        text = None
    text = _scrub(str(text or exc.reason or "no details"), key).strip()
    return text[:_REASON_LIMIT]


def _reach_hint(provider: Provider) -> str:
    if provider.local:
        return f"Check that {provider.label} is running and the base URL is right."
    return "Check your network connection and the base URL."
