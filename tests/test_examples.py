"""Examples are documentation people copy from: they must at least parse, explain themselves,
fail politely without arguments, and be listed in the examples index."""

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
EXAMPLES = sorted((ROOT / "examples").glob("[0-9]*.py"))
NEEDS = {"05_websocket_client.py": "websockets", "06_mcp_client.py": "mcp"}


def test_the_expected_examples_exist() -> None:
    assert len(EXAMPLES) >= 8


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_parses_and_documents_how_to_run_it(path: Path) -> None:
    doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
    assert doc, f"{path.name} needs a docstring"
    assert "python examples/" in doc, f"{path.name}: the docstring must show the command to run it"


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_prints_usage_and_fails_without_arguments(path: Path) -> None:
    module = NEEDS.get(path.name)
    if module and importlib.util.find_spec(module) is None:
        pytest.skip(f"{module} is not installed (extra not selected)")
    result = subprocess.run(  # noqa: S603 - our own script, fixed arguments
        [sys.executable, str(path)], capture_output=True, text=True, encoding="utf-8", timeout=60
    )
    assert result.returncode != 0
    assert "python examples/" in result.stderr


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_every_example_is_listed_in_the_examples_index(path: Path) -> None:
    assert path.name in (ROOT / "examples" / "README.md").read_text(encoding="utf-8")


def test_the_main_readme_points_to_the_examples_index() -> None:
    assert "examples/README.md" in (ROOT / "README.md").read_text(encoding="utf-8")
