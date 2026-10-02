import asyncio
import wave
from pathlib import Path
from typing import Any

import pytest

from tests.fakes import FakeRecognizer, FakeSynthesizer
from tests.test_audio import make_wav
from voxar import Voxar
from voxar.mcp_server import build_server, resolve_inside

pytest.importorskip("mcp")
from mcp import Client  # noqa: E402


def test_resolve_inside_accepts_paths_under_an_allowed_directory(tmp_path: Path) -> None:
    inside = tmp_path / "a" / "x.wav"
    assert resolve_inside(str(inside), [tmp_path]) == inside.resolve()


def test_resolve_inside_rejects_other_directories(tmp_path: Path) -> None:
    other = tmp_path.parent / "elsewhere.wav"
    with pytest.raises(ValueError, match="outside the allowed"):
        resolve_inside(str(other), [tmp_path])


def test_resolve_inside_rejects_dotdot_escapes(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside the allowed"):
        resolve_inside(str(tmp_path / ".." / "etc" / "passwd"), [tmp_path])


def test_resolve_inside_rejects_symlink_escapes(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside_dir_for_test"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="outside the allowed"):
        resolve_inside(str(link / "x.wav"), [tmp_path])


def server(tmp_path: Path) -> Any:
    app = Voxar(recognizer=FakeRecognizer(), synthesizer=FakeSynthesizer(), chunk_ms=250)
    return build_server(
        app,
        allowed_dirs=[tmp_path],
        engines=lambda: {"recognizers": ["fake"], "synthesizers": ["fake"]},
    )


def call(srv: Any, tool: str, arguments: dict[str, Any]) -> Any:
    async def run() -> Any:
        async with Client(srv) as client:
            return await client.call_tool(tool, arguments)

    return asyncio.run(run())


def test_the_server_exposes_exactly_the_documented_tools(tmp_path: Path) -> None:
    async def run() -> set[str]:
        async with Client(server(tmp_path)) as client:
            return {tool.name for tool in (await client.list_tools()).tools}

    assert asyncio.run(run()) == {"transcribe_file", "speak", "list_engines"}


def test_transcribe_file_returns_text(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "a.wav", seconds=0.5)
    result = call(server(tmp_path), "transcribe_file", {"path": str(wav)})
    assert not result.is_error
    assert "line0:8000 line1:8000" in str(result.structured_content)


def test_transcribe_file_outside_allowed_dirs_is_an_error(tmp_path: Path) -> None:
    outside = make_wav(tmp_path.parent / "outside_mcp_test.wav")
    try:
        result = call(server(tmp_path), "transcribe_file", {"path": str(outside)})
    finally:
        outside.unlink()
    assert result.is_error
    assert "outside the allowed" in str(result.content)


def test_speak_writes_a_wav(tmp_path: Path) -> None:
    target = tmp_path / "out.wav"
    result = call(server(tmp_path), "speak", {"text": "abc", "output_path": str(target)})
    assert not result.is_error
    with wave.open(str(target), "rb") as handle:
        assert handle.getnframes() == 160 * 3


def test_speak_refuses_to_overwrite_unless_asked(tmp_path: Path) -> None:
    target = tmp_path / "out.wav"
    target.write_bytes(b"keep me")
    refused = call(server(tmp_path), "speak", {"text": "abc", "output_path": str(target)})
    assert refused.is_error
    assert target.read_bytes() == b"keep me"
    allowed = call(
        server(tmp_path),
        "speak",
        {"text": "abc", "output_path": str(target), "overwrite": True},
    )
    assert not allowed.is_error


def test_speak_outside_allowed_dirs_is_refused(tmp_path: Path) -> None:
    target = tmp_path.parent / "outside_speak_test.wav"
    result = call(server(tmp_path), "speak", {"text": "abc", "output_path": str(target)})
    assert result.is_error
    assert not target.exists()


def test_list_engines(tmp_path: Path) -> None:
    result = call(server(tmp_path), "list_engines", {})
    assert not result.is_error
    assert "fake" in str(result.structured_content)
