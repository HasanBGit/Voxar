from importlib.metadata import version

import voxar


def test_version_has_a_single_source_of_truth() -> None:
    """pyproject.toml reads the version from voxar.__version__, so installed metadata must agree."""
    assert voxar.__version__ == version("voxar")
