"""The single source of configuration. Environment first, explicit values override in code."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from voxar.domain import ConfigError

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class Config:
    cache_dir: Path
    offline: bool = False
    recognizer: str = "moonshine"
    synthesizer: str | None = None

    def __post_init__(self) -> None:
        if not self.recognizer:
            raise ConfigError("recognizer name must not be empty (VOXAR_RECOGNIZER)")
        if self.synthesizer is not None and not self.synthesizer:
            raise ConfigError("synthesizer name must not be empty (VOXAR_SYNTHESIZER)")

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Config":
        return cls(
            cache_dir=_cache_dir(env),
            offline=_parse_bool("VOXAR_OFFLINE", env.get("VOXAR_OFFLINE", "")),
            recognizer=env.get("VOXAR_RECOGNIZER", "moonshine"),
            synthesizer=env.get("VOXAR_SYNTHESIZER") or None,
        )


def _cache_dir(env: Mapping[str, str]) -> Path:
    if explicit := env.get("VOXAR_CACHE_DIR"):
        return Path(explicit)
    if xdg := env.get("XDG_CACHE_HOME"):
        return Path(xdg) / "voxar"
    home = env.get("HOME") or env.get("USERPROFILE")
    if home:
        return Path(home) / ".cache" / "voxar"
    raise ConfigError("cannot find a cache directory: set VOXAR_CACHE_DIR")


def _parse_bool(name: str, raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigError(f"{name} must be one of 1/0/true/false/yes/no/on/off, got {raw!r}")
