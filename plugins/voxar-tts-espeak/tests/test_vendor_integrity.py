"""Vendored third-party files must not change without MANIFEST.md being updated."""

import hashlib
import re
from pathlib import Path

VENDOR = Path(__file__).parent.parent / "src" / "voxar_tts_espeak" / "_vendor"


def test_vendored_files_match_the_manifest() -> None:
    rows = re.findall(
        r"\| `([^`]+)` \| `[0-9a-f]{64}` \| `([0-9a-f]{64})` \|",
        (VENDOR / "MANIFEST.md").read_text(),
    )
    assert len(rows) == 5
    for name, expected in rows:
        actual = hashlib.sha256((VENDOR / name).read_bytes()).hexdigest()
        assert actual == expected, f"{name} changed; update MANIFEST.md and UPSTREAM.md"


def test_no_network_download_helpers_are_left_in_vendored_code() -> None:
    for path in VENDOR.rglob("*.py"):
        text = path.read_text()
        assert "hf_hub_download" not in text, path
        assert "urllib" not in text and "requests" not in text, path
