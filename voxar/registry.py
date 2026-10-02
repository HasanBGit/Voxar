"""Find engines by name. Engines register in code or through entry points.

Entry-point groups: ``voxar.recognizers`` and ``voxar.synthesizers``. An entry point loads a
factory ``Callable[[Config], engine]``. Engines are imported only when asked for, so listing
what is available never imports a speech library.
"""

from collections.abc import Callable, Mapping
from importlib.metadata import entry_points
from typing import Any

from voxar.config import Config
from voxar.domain import EngineUnavailableError
from voxar.ports import SpeechRecognizer, SpeechSynthesizer

RECOGNIZER_GROUP = "voxar.recognizers"
SYNTHESIZER_GROUP = "voxar.synthesizers"

Factory = Callable[[Config], Any]
Loaders = Mapping[str, Callable[[], Factory]]
Discover = Callable[[str], Loaders]


def _entry_point_loaders(group: str) -> Loaders:
    return {ep.name: ep.load for ep in entry_points(group=group)}


class Registry:
    def __init__(self, discover: Discover = _entry_point_loaders) -> None:
        self._discover = discover
        self._recognizers: dict[str, Factory] = {}
        self._synthesizers: dict[str, Factory] = {}

    def register_recognizer(self, name: str, factory: Factory) -> None:
        self._recognizers[name] = factory

    def register_synthesizer(self, name: str, factory: Factory) -> None:
        self._synthesizers[name] = factory

    def recognizer(self, name: str, config: Config) -> SpeechRecognizer:
        engine = self._create("recognizer", RECOGNIZER_GROUP, self._recognizers, name, config)
        if not isinstance(engine, SpeechRecognizer):
            raise EngineUnavailableError(f"engine {name!r} does not implement SpeechRecognizer")
        return engine

    def synthesizer(self, name: str, config: Config) -> SpeechSynthesizer:
        engine = self._create("synthesizer", SYNTHESIZER_GROUP, self._synthesizers, name, config)
        if not isinstance(engine, SpeechSynthesizer):
            raise EngineUnavailableError(f"engine {name!r} does not implement SpeechSynthesizer")
        return engine

    def available(self) -> dict[str, list[str]]:
        return {
            "recognizers": self._names(RECOGNIZER_GROUP, self._recognizers),
            "synthesizers": self._names(SYNTHESIZER_GROUP, self._synthesizers),
        }

    def _names(self, group: str, explicit: Mapping[str, Factory]) -> list[str]:
        return sorted({*explicit, *self._discover(group)})

    def _create(
        self, kind: str, group: str, explicit: Mapping[str, Factory], name: str, config: Config
    ) -> object:
        if name in explicit:
            return explicit[name](config)
        loaders = self._discover(group)
        if name in loaders:
            return loaders[name]()(config)
        names = self._names(group, explicit)
        raise EngineUnavailableError(
            f"no {kind} named {name!r}. Available: {', '.join(names) or 'none'}. "
            f"Install a package that provides it (see the README) or set VOXAR_{kind.upper()}."
        )
