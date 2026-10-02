from pathlib import Path

import pytest

from voxar.config import Config
from voxar.domain import ConfigError


def test_defaults_use_home_cache() -> None:
    config = Config.from_env({"HOME": "/home/u"})
    assert config.cache_dir == Path("/home/u/.cache/voxar")
    assert config.offline is False
    assert config.recognizer == "moonshine"
    assert config.synthesizer is None


def test_xdg_cache_home_is_respected() -> None:
    config = Config.from_env({"XDG_CACHE_HOME": "/x", "HOME": "/home/u"})
    assert config.cache_dir == Path("/x/voxar")


def test_voxar_variables_override() -> None:
    config = Config.from_env(
        {
            "HOME": "/h",
            "VOXAR_CACHE_DIR": "/models",
            "VOXAR_OFFLINE": "yes",
            "VOXAR_RECOGNIZER": "other",
            "VOXAR_SYNTHESIZER": "nabra",
        }
    )
    assert config == Config(
        cache_dir=Path("/models"), offline=True, recognizer="other", synthesizer="nabra"
    )


@pytest.mark.parametrize(
    ("raw", "expected"), [("1", True), ("true", True), ("0", False), ("no", False)]
)
def test_offline_flag_parsing(raw: str, expected: bool) -> None:
    assert Config.from_env({"HOME": "/h", "VOXAR_OFFLINE": raw}).offline is expected


def test_invalid_offline_value_fails_fast() -> None:
    with pytest.raises(ConfigError, match="VOXAR_OFFLINE"):
        Config.from_env({"HOME": "/h", "VOXAR_OFFLINE": "maybe"})


def test_empty_engine_name_is_rejected() -> None:
    with pytest.raises(ConfigError, match="recognizer"):
        Config(cache_dir=Path("/c"), recognizer="")


def test_no_home_and_no_cache_dir_fails_fast() -> None:
    with pytest.raises(ConfigError, match="VOXAR_CACHE_DIR"):
        Config.from_env({})


def test_empty_synthesizer_name_is_rejected() -> None:
    with pytest.raises(ConfigError, match="synthesizer"):
        Config(cache_dir=Path("/c"), synthesizer="")
