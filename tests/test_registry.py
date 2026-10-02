from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from tests.fakes import FakeRecognizer, FakeSynthesizer
from voxar.config import Config
from voxar.domain import EngineUnavailableError
from voxar.ports import SpeechRecognizer, SpeechSynthesizer
from voxar.registry import Registry

CONFIG = Config(cache_dir=Path("/c"))


def no_entry_points(_: str) -> Mapping[str, Callable[[], Callable[[Config], object]]]:
    return {}


def test_registered_recognizer_is_created_with_config() -> None:
    seen: list[Config] = []

    def factory(config: Config) -> SpeechRecognizer:
        seen.append(config)
        return FakeRecognizer()

    registry = Registry(discover=no_entry_points)
    registry.register_recognizer("fake", factory)
    assert isinstance(registry.recognizer("fake", CONFIG), FakeRecognizer)
    assert seen == [CONFIG]


def test_registered_synthesizer() -> None:
    registry = Registry(discover=no_entry_points)
    registry.register_synthesizer("fake", lambda _: FakeSynthesizer())
    assert isinstance(registry.synthesizer("fake", CONFIG), FakeSynthesizer)


def test_unknown_engine_fails_with_actionable_message() -> None:
    registry = Registry(discover=no_entry_points)
    registry.register_recognizer("fake", lambda _: FakeRecognizer())
    with pytest.raises(EngineUnavailableError) as info:
        registry.recognizer("missing", CONFIG)
    message = str(info.value)
    assert "missing" in message
    assert "fake" in message  # lists what is available
    assert "install" in message.lower()


def test_entry_point_engines_are_loaded_lazily() -> None:
    loaded: list[str] = []

    def discover(group: str) -> Mapping[str, Callable[[], Callable[[Config], object]]]:
        if group != "voxar.recognizers":
            return {}

        def load() -> Callable[[Config], object]:
            loaded.append("moonshine")
            return lambda _: FakeRecognizer()

        return {"moonshine": load}

    registry = Registry(discover=discover)
    assert registry.available()["recognizers"] == ["moonshine"]
    assert loaded == []  # listing does not import the engine
    assert isinstance(registry.recognizer("moonshine", CONFIG), FakeRecognizer)
    assert loaded == ["moonshine"]


def test_wrong_kind_returned_by_plugin_is_rejected() -> None:
    registry = Registry(discover=no_entry_points)
    registry.register_recognizer("bad", lambda _: object())
    with pytest.raises(EngineUnavailableError, match="SpeechRecognizer"):
        registry.recognizer("bad", CONFIG)


def test_synthesizer_type_check() -> None:
    registry = Registry(discover=no_entry_points)
    registry.register_synthesizer("bad", lambda _: FakeRecognizer())
    with pytest.raises(EngineUnavailableError, match="SpeechSynthesizer"):
        registry.synthesizer("bad", CONFIG)


def test_protocols_are_runtime_checkable() -> None:
    assert isinstance(FakeRecognizer(), SpeechRecognizer)
    assert isinstance(FakeSynthesizer(), SpeechSynthesizer)


def test_default_discovery_uses_entry_points_without_failing() -> None:
    available = Registry().available()
    assert set(available) == {"recognizers", "synthesizers"}
