"""The READMEs are documentation users copy from: their commands must be real and links alive."""

import re
import shlex
from pathlib import Path

import pytest

from voxar.cli import _parser

ROOT = Path(__file__).parent.parent
ENGLISH = ROOT / "README.md"
ARABIC = ROOT / "docs" / "translations" / "README.ar-SA.md"
READMES = [ENGLISH, ARABIC]

FENCE = re.compile(r"^```[a-z]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
COMMAND = re.compile(r"^\s*(?:\$ )?(?:[A-Z_]+=\S+ )*(?:uv run )?voxar (?P<args>.+)$")
LINK = re.compile(r"\]\((?P<target>[^)\s]+)\)")
ASSET = re.compile(r'(?:src|srcset)="(?P<target>[^"]+)"')


def code_blocks(path: Path) -> list[str]:
    return [block.strip("\n") for block in FENCE.findall(path.read_text())]


def voxar_commands(path: Path) -> list[str]:
    commands = []
    for block in code_blocks(path):
        for line in block.splitlines():
            match = COMMAND.match(line.split("  #")[0].rstrip())
            if match:
                commands.append(match.group("args"))
    return commands


@pytest.mark.parametrize("path", READMES, ids=lambda p: p.parent.name + "/" + p.name)
def test_every_voxar_command_in_the_readme_parses_against_the_real_cli(path: Path) -> None:
    commands = voxar_commands(path)
    assert commands, "expected example commands in the README"
    for args in commands:
        tokens = shlex.split(args)
        if tokens[0].startswith("[") or tokens[0].startswith("{"):
            continue  # the usage synopsis line, not a runnable command
        try:
            _parser().parse_args(tokens)
        except SystemExit as exit_:
            if exit_.code != 0:  # --version and --help exit 0 after printing: those are valid
                pytest.fail(f"README command is not valid for the CLI: voxar {args}")


@pytest.mark.parametrize("path", READMES, ids=lambda p: p.parent.name + "/" + p.name)
def test_relative_links_point_to_files_that_exist(path: Path) -> None:
    missing = []
    for match in LINK.finditer(path.read_text()):
        target = match.group("target")
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue
        if not (path.parent / target.split("#")[0]).exists():
            missing.append(target)
    assert missing == []


def test_in_page_anchors_resolve_in_the_english_readme() -> None:
    text = ENGLISH.read_text()
    headings = {
        re.sub(r"[^\w\s-]", "", h.lower()).strip().replace(" ", "-")
        for h in re.findall(r"^#{1,6} (.+)$", text, re.MULTILINE)
    }
    anchors = {a for a in re.findall(r"\]\(#([^)]+)\)", text)}
    assert anchors - headings == set()


def test_the_arabic_readme_cannot_drift_from_the_english_code_blocks() -> None:
    english = set(code_blocks(ENGLISH))
    unknown = [block for block in code_blocks(ARABIC) if block not in english]
    assert unknown == []


def test_the_readme_has_no_claims_about_things_that_do_not_exist() -> None:
    text = ENGLISH.read_text().lower()
    for fake in ("trendshift", "pypi.org/project", "discord.gg", "y combinator", "contrib.rocks"):
        assert fake not in text


@pytest.mark.parametrize("path", READMES, ids=lambda p: p.parent.name + "/" + p.name)
def test_images_referenced_by_the_readme_exist(path: Path) -> None:
    local = [
        m.group("target")
        for m in ASSET.finditer(path.read_text())
        if not re.match(r"^[a-z]+:", m.group("target"))
    ]
    assert local, "expected the README to show the logo"
    assert [t for t in local if not (path.parent / t).exists()] == []


def test_links_in_the_examples_index_exist() -> None:
    index = ROOT / "examples" / "README.md"
    missing = []
    for match in LINK.finditer(index.read_text()):
        target = match.group("target")
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue
        if not (index.parent / target.split("#")[0]).exists():
            missing.append(target)
    assert missing == []
