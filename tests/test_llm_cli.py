"""`voxar llm ...` and the environment-driven client factory, against a local fake provider."""

import io
from pathlib import Path

import pytest

from tests.fake_llm import FakeLLMServer, json_reply, openai_message, openai_stream, sse_reply
from voxar.cli import main
from voxar.config import Config
from voxar.domain import ConfigError, OfflineModeError
from voxar.llm import PROVIDERS, ChatClient, client_from_config, provider_named

KEY = "sk-test-secret-1234567890"


def run(
    argv: list[str], tmp_path: Path, server: FakeLLMServer | None = None, **env: str
) -> tuple[int, str, str]:
    """Run the CLI with the `custom` provider pointed at the fake server."""
    out, err = io.StringIO(), io.StringIO()
    environment = {"HOME": str(tmp_path), "VOXAR_LLM_API_KEY": KEY, **env}
    code = main(argv, env=environment, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def custom(server: FakeLLMServer, *argv: str) -> list[str]:
    return ["--provider", "custom", "--base-url", server.base_url, *argv]


def test_ask_streams_the_reply_and_ends_with_a_newline(tmp_path: Path) -> None:
    with FakeLLMServer(lambda *_: sse_reply(openai_stream(["أهلاً ", "وسهلاً"]))) as server:
        code, out, _ = run(["llm", "ask", "مرحبا", *custom(server, "--model", "m1")], tmp_path)
    assert (code, out) == (0, "أهلاً وسهلاً\n")
    assert server.requests[0]["body"]["messages"] == [{"role": "user", "content": "مرحبا"}]


def test_ask_no_stream_sends_the_system_prompt(tmp_path: Path) -> None:
    with FakeLLMServer(lambda *_: json_reply(openai_message("تمام"))) as server:
        argv = ["llm", "ask", "hi", "--no-stream", "--system", "كن مختصرًا", "--max-tokens", "9"]
        code, out, _ = run([*argv, *custom(server, "--model", "m1")], tmp_path)
    body = server.requests[0]["body"]
    assert (code, out) == (0, "تمام\n")
    assert body["messages"][0] == {"role": "system", "content": "كن مختصرًا"}
    assert body["max_tokens"] == 9
    assert "stream" not in body


def test_models_lists_without_needing_a_model_name(tmp_path: Path) -> None:
    with FakeLLMServer(lambda *_: json_reply({"data": [{"id": "b"}, {"id": "a"}]})) as server:
        code, out, _ = run(["llm", "models", *custom(server)], tmp_path)
    assert (code, out) == (0, "a\nb\n")


def test_a_provider_error_is_one_readable_line(tmp_path: Path) -> None:
    with FakeLLMServer(lambda *_: json_reply({"error": {"message": "no"}}, 401)) as server:
        code, out, err = run(["llm", "ask", "hi", *custom(server, "--model", "m")], tmp_path)
    assert code == 2
    assert out == ""
    assert err.startswith("error: the custom endpoint rejected the API key")
    assert KEY not in err


def test_ask_needs_a_model_when_the_provider_has_no_default(tmp_path: Path) -> None:
    code, _, err = run(["llm", "ask", "hi", "--provider", "openrouter"], tmp_path)
    assert code == 2
    assert "--model" in err
    assert "voxar llm models --provider openrouter" in err


def test_a_missing_key_names_the_environment_variable(tmp_path: Path) -> None:
    code, _, err = run(["llm", "ask", "hi"], tmp_path)  # default provider is humain
    assert code == 2
    assert "HUMAIN_NODE_API_KEY" in err


def test_providers_shows_whether_a_key_is_set_but_never_the_key(tmp_path: Path) -> None:
    code, out, _ = run(["llm", "providers"], tmp_path, HUMAIN_NODE_API_KEY=KEY)
    humain = next(line for line in out.splitlines() if line.startswith("humain"))
    assert code == 0
    assert "HUMAIN_NODE_API_KEY (set)" in humain
    assert "OPENROUTER_API_KEY (not set)" in out
    assert KEY not in out
    assert {line.split()[0] for line in out.splitlines()} == set(PROVIDERS)


def test_offline_mode_refuses_remote_providers(tmp_path: Path) -> None:
    code, _, err = run(["llm", "ask", "hi"], tmp_path, VOXAR_OFFLINE="1")
    assert code == 2
    assert "VOXAR_OFFLINE" in err


def test_offline_mode_allows_loopback(tmp_path: Path) -> None:
    config = Config.from_env({"HOME": str(tmp_path), "VOXAR_OFFLINE": "1"})
    client = client_from_config(config, {}, provider="ollama", model="llama")
    assert isinstance(client, ChatClient)
    with pytest.raises(OfflineModeError):
        client_from_config(config, {}, provider="openrouter", model="x")


def test_factory_precedence_is_argument_then_environment_then_provider_default() -> None:
    env = {
        "HOME": "/h",
        "VOXAR_LLM_PROVIDER": "ollama",
        "VOXAR_LLM_MODEL": "from-env",
        "VOXAR_LLM_BASE_URL": "http://localhost:9999/v1",
    }
    config = Config.from_env(env)
    assert client_from_config(config, env).model == "from-env"
    assert client_from_config(config, env, model="flag").model == "flag"
    assert client_from_config(
        Config.from_env({"HOME": "/h"}), {"HUMAIN_NODE_API_KEY": "k"}
    ).model == (provider_named("humain").default_model)


def test_an_empty_key_in_the_environment_counts_as_missing() -> None:
    config = Config.from_env({"HOME": "/h"})
    with pytest.raises(ConfigError, match="HUMAIN_NODE_API_KEY"):
        client_from_config(config, {"HUMAIN_NODE_API_KEY": ""})
