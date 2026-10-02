"""Run real examples against the real model. Opt-in: needs the model pulled and a real
16 kHz mono WAV, e.g. VOXAR_TEST_WAV=sample.wav pytest -m integration"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from voxar.config import Config
from voxar.engines.moonshine import MODEL_ID
from voxar.models import CATALOG, ModelStore

pytestmark = pytest.mark.integration
ROOT = Path(__file__).parent.parent


@pytest.fixture
def wav() -> Path:
    path = os.environ.get("VOXAR_TEST_WAV")
    if not path or not Path(path).is_file():
        pytest.skip("set VOXAR_TEST_WAV to a real 16 kHz mono 16-bit WAV")
    config = Config.from_env(os.environ)
    if not ModelStore(config.cache_dir, offline=True).is_installed(CATALOG[MODEL_ID]):
        pytest.skip(f"model not installed: voxar models pull {MODEL_ID} --accept-license")
    return Path(path)


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - our own examples
        [sys.executable, *args], capture_output=True, text=True, timeout=300, env=os.environ
    )


def test_transcribe_file_example(wav: Path) -> None:
    result = run(str(ROOT / "examples" / "01_transcribe_file.py"), str(wav))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()
    assert result.stderr == ""  # no native diagnostics leak through


def test_stream_example_ends_with_a_final_event(wav: Path) -> None:
    result = run(str(ROOT / "examples" / "02_stream_from_wav.py"), str(wav))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1].startswith("final")


def test_batch_example_records_bad_files_and_continues(wav: Path, tmp_path: Path) -> None:
    folder = tmp_path / "in"
    folder.mkdir()
    shutil.copy(wav, folder / "good.wav")
    (folder / "bad.wav").write_bytes(b"not audio")
    out = tmp_path / "out.jsonl"
    result = run(str(ROOT / "examples" / "07_batch_transcribe.py"), str(folder), str(out))
    assert result.returncode == 0, result.stderr
    rows = {r["file"]: r for r in map(json.loads, out.read_text().splitlines())}
    assert "error" in rows["bad.wav"]
    assert rows["good.wav"]["text"] and rows["good.wav"]["rtf"] > 0


def test_mcp_client_example(wav: Path) -> None:
    pytest.importorskip("mcp")
    result = run(str(ROOT / "examples" / "06_mcp_client.py"), str(wav))
    assert result.returncode == 0, result.stderr
    assert "transcribe_file" in result.stdout
    assert "text:" in result.stdout
