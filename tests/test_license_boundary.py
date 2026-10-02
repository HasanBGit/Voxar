"""ADR 0002: the Apache-2.0 core must never import the GPL-3.0 TTS plugin or its GPL stack."""

import ast
from pathlib import Path

CORE = Path(__file__).parent.parent / "voxar"
FORBIDDEN = {"voxar_tts_espeak", "phonemizer", "espeakng_loader", "misaki", "torch", "transformers"}


def imported_top_level_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_core_never_imports_the_gpl_plugin_or_its_stack() -> None:
    offenders = {
        str(path.relative_to(CORE)): sorted(imported_top_level_names(path) & FORBIDDEN)
        for path in CORE.rglob("*.py")
        if imported_top_level_names(path) & FORBIDDEN
    }
    assert offenders == {}
