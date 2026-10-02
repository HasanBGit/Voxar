import json
from typing import Any

import pytest

from tests.fake_llm import (
    FakeLLMServer,
    Reply,
    anthropic_stream,
    json_reply,
    openai_message,
    openai_stream,
    sse_reply,
)
from voxar.domain import ConfigError, LLMError
from voxar.llm import PROVIDERS, ChatClient, Message, provider_named

KEY = "sk-test-secret-1234567890"
HELLO = [Message("user", "مرحبا")]


def client(server: FakeLLMServer, provider: str = "custom", **kwargs: Any) -> ChatClient:
    return ChatClient(
        provider_named(provider), model="m1", base_url=server.base_url, api_key=KEY, **kwargs
    )


def test_reply_sends_the_documented_request_and_returns_the_content() -> None:
    def responder(path: str, body: dict[str, Any], headers: dict[str, str]) -> Reply:
        return json_reply(openai_message("أهلاً وسهلاً"))

    with FakeLLMServer(responder) as server:
        text = client(server).reply(HELLO, system="كن مختصرًا", max_tokens=77)
    sent = server.requests[0]
    assert text == "أهلاً وسهلاً"
    assert sent["path"] == "/v1/chat/completions"
    assert sent["body"]["model"] == "m1"
    assert sent["body"]["max_tokens"] == 77
    assert sent["body"]["messages"] == [
        {"role": "system", "content": "كن مختصرًا"},
        {"role": "user", "content": "مرحبا"},
    ]
    assert sent["headers"]["authorization"] == f"Bearer {KEY}"
    assert sent["headers"]["user-agent"].startswith("voxar/")  # gateways block the default Python agent


def test_reasoning_content_is_never_spoken() -> None:
    with FakeLLMServer(lambda *_: json_reply(openai_message("الجواب", reasoning_content="thinking..."))) as s:
        assert client(s).reply(HELLO) == "الجواب"


@pytest.mark.parametrize("content", [None, "", "   "])
def test_an_empty_reply_is_an_error_not_silence(content: str | None) -> None:
    with FakeLLMServer(lambda *_: json_reply(openai_message(content))) as server:
        with pytest.raises(LLMError, match="empty reply"):
            client(server).reply(HELLO)


def test_unparseable_responses_are_reported() -> None:
    with FakeLLMServer(lambda *_: (200, {"Content-Type": "text/html"}, b"<html>oops</html>")) as server:
        with pytest.raises(LLMError, match="unexpected response"):
            client(server).reply(HELLO)


@pytest.mark.parametrize(
    ("status", "headers", "expected"),
    [
        (401, {}, "rejected the API key"),
        (403, {}, "denied"),
        (404, {}, "voxar llm models"),
        (429, {"Retry-After": "7"}, "retry after 7"),
        (500, {}, "unavailable"),
        (503, {"X-Request-ID": "req-42"}, "req-42"),
    ],
)
def test_http_errors_become_actionable_messages(
    status: int, headers: dict[str, str], expected: str
) -> None:
    with FakeLLMServer(lambda *_: json_reply({"error": {"message": "boom"}}, status, **headers)) as s:
        with pytest.raises(LLMError, match=expected) as info:
            client(s).reply(HELLO)
    assert KEY not in str(info.value)  # the key must never reach an error message


def test_a_bad_request_shows_the_providers_reason() -> None:
    body = {"error": {"message": "Unsupported parameter(s): `reasoning`"}}
    with FakeLLMServer(lambda *_: json_reply(body, 400)) as server:
        with pytest.raises(LLMError, match="Unsupported parameter"):
            client(server).reply(HELLO)


def test_connection_failure_says_what_to_check() -> None:
    dead = ChatClient(provider_named("ollama"), model="m", base_url="http://127.0.0.1:9/v1", api_key=None)
    with pytest.raises(LLMError, match="Ollama"):
        dead.reply(HELLO)


def test_stream_yields_text_pieces_in_order() -> None:
    with FakeLLMServer(lambda *_: sse_reply(openai_stream(["أهلاً ", "وسهلاً", ""]))) as server:
        pieces = list(client(server).stream(HELLO))
        sent = server.requests[0]["body"]
    assert "".join(pieces) == "أهلاً وسهلاً"
    assert sent["stream"] is True


def test_models_lists_ids_from_the_provider() -> None:
    with FakeLLMServer(lambda *_: json_reply({"data": [{"id": "b"}, {"id": "a"}]})) as server:
        assert client(server).models() == ["a", "b"]
        assert server.requests[0]["method"] == "GET"


def test_anthropic_uses_its_own_protocol() -> None:
    def responder(path: str, body: dict[str, Any], headers: dict[str, str]) -> Reply:
        return json_reply({"content": [{"type": "text", "text": "مرحبا بك"}, {"type": "text", "text": "!"}]})

    with FakeLLMServer(responder) as server:
        text = client(server, "anthropic").reply(HELLO, system="sys")
    sent = server.requests[0]
    assert text == "مرحبا بك!"
    assert sent["path"] == "/v1/messages"
    assert sent["headers"]["x-api-key"] == KEY
    assert "authorization" not in sent["headers"]
    assert sent["headers"]["anthropic-version"]
    assert sent["body"]["system"] == "sys"
    assert sent["body"]["messages"] == [{"role": "user", "content": "مرحبا"}]
    assert sent["body"]["max_tokens"] > 0


def test_anthropic_stream() -> None:
    with FakeLLMServer(lambda *_: sse_reply(anthropic_stream(["a", "b"]))) as server:
        assert "".join(client(server, "anthropic").stream(HELLO)) == "ab"


def test_remote_providers_must_use_https() -> None:
    with pytest.raises(ConfigError, match="https"):
        ChatClient(provider_named("custom"), model="m", base_url="http://example.com/v1", api_key=KEY)


def test_http_is_allowed_for_loopback_only() -> None:
    ChatClient(provider_named("ollama"), model="m", base_url="http://localhost:11434/v1", api_key=None)
    ChatClient(provider_named("ollama"), model="m", base_url="http://[::1]:11434/v1", api_key=None)


def test_a_key_is_required_for_hosted_providers() -> None:
    with pytest.raises(ConfigError, match="HUMAIN_NODE_API_KEY"):
        ChatClient(provider_named("humain"), model="m", base_url=None, api_key=None)


def test_unknown_provider_lists_the_known_ones() -> None:
    with pytest.raises(ConfigError, match="humain"):
        provider_named("nope")


def test_provider_presets() -> None:
    humain = PROVIDERS["humain"]
    assert humain.base_url == "https://api.node.humain.com/v1"
    assert humain.key_env == "HUMAIN_NODE_API_KEY"
    assert humain.streaming is False  # measured: the gateway answers "Streaming is not supported"
    assert humain.default_model == "humain-m3-preview"
    assert PROVIDERS["openrouter"].base_url == "https://openrouter.ai/api/v1"
    assert PROVIDERS["ollama"].local and PROVIDERS["lmstudio"].local
    assert not PROVIDERS["openai"].local


def test_messages_are_validated() -> None:
    with pytest.raises(ValueError, match="role"):
        Message("system", "x")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="empty"):
        Message("user", "  ")


def test_json_body_is_utf8_arabic() -> None:
    with FakeLLMServer(lambda *_: json_reply(openai_message("x"))) as server:
        client(server).reply([Message("user", "الدرعية")])
    assert json.dumps(server.requests[0]["body"], ensure_ascii=False).count("الدرعية") == 1
