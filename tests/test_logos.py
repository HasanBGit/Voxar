"""The logos are generated from scripts/make_logos.py; the files on disk must match it."""

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "assets"
NAMES = ["logo.svg", "logo-dark.svg", "logo-mark.svg", "logo-mark-dark.svg"]


@pytest.mark.parametrize("name", NAMES)
def test_logo_is_well_formed_svg_with_a_title_and_label(name: str) -> None:
    root = ET.parse(ASSETS / name).getroot()  # noqa: S314 - our own committed file
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.get("aria-label") == "voxar"
    assert root.find("{http://www.w3.org/2000/svg}title") is not None


@pytest.mark.parametrize("name", NAMES)
def test_logo_has_no_external_references_or_scripts(name: str) -> None:
    text = (ASSETS / name).read_text(encoding="utf-8").lower()
    for forbidden in (
        "<script",
        "href=",
        "<image",
        "<foreignobject",
        "@import",
        "http://",
        "https://",
    ):
        # the only allowed URL is the SVG namespace declaration
        assert forbidden not in text.replace('xmlns="http://www.w3.org/2000/svg"', "")


def test_logo_files_match_the_generator() -> None:
    result = subprocess.run(  # noqa: S603 - fixed arguments, our own script
        [sys.executable, str(ROOT / "scripts" / "make_logos.py"), "--check"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
