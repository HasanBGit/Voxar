import asyncio
import struct
import wave
from pathlib import Path
from typing import Any

import pytest

from tests.fakes import FakeRecognizer, FakeSynthesizer
from tests.test_audio import make_wav
from voxar import Voxar
from voxar.domain import AudioChunk
from voxar.mcp_server import build_server, resolve_inside
from voxar.voice import VoiceIO

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


# --- voice tools (--voice): speakers and microphone, injected so no device is needed ---


class FakeDevices:
    def __init__(self, phrases: list[list[AudioChunk]] | None = None) -> None:
        self.played: list[Any] = []
        self.opened = 0
        self._phrases = list(phrases or [])

    def play(self, audio: Any) -> None:
        self.played.append(audio)

    def listen_chunks(self) -> Any:
        self.opened += 1
        return iter(self._phrases.pop(0) if self._phrases else [])


def speech(blocks: int = 3) -> list[AudioChunk]:
    loud = AudioChunk(pcm=struct.pack("<h", 3000) * 1600)
    quiet = AudioChunk(pcm=bytes(3200))
    return [loud] * blocks + [quiet] * 20


def voice_server(tmp_path: Path, devices: FakeDevices) -> Any:
    app = Voxar(recognizer=FakeRecognizer(), synthesizer=FakeSynthesizer(), chunk_ms=250)
    return build_server(
        app,
        allowed_dirs=[tmp_path],
        engines=lambda: {"recognizers": ["fake"], "synthesizers": ["fake"]},
        voice=VoiceIO(play=devices.play, listen_chunks=devices.listen_chunks),
    )


def test_voice_tools_exist_only_with_the_voice_option(tmp_path: Path) -> None:
    async def names(srv: Any) -> set[str]:
        async with Client(srv) as client:
            return {tool.name for tool in (await client.list_tools()).tools}

    assert asyncio.run(names(voice_server(tmp_path, FakeDevices()))) == {
        "transcribe_file",
        "speak",
        "list_engines",
        "announce",
        "listen",
        "ask",
    }
    assert "announce" not in asyncio.run(names(server(tmp_path)))


def test_announce_speaks_on_the_speakers_and_writes_no_file(tmp_path: Path) -> None:
    devices = FakeDevices()
    result = call(voice_server(tmp_path, devices), "announce", {"message": "خلصت"})
    assert not result.is_error
    assert len(devices.played) == 1
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("message", ["", "   ", "x" * 501])
def test_announce_rejects_empty_and_long_messages(tmp_path: Path, message: str) -> None:
    devices = FakeDevices()
    result = call(voice_server(tmp_path, devices), "announce", {"message": message})
    assert result.is_error
    assert devices.played == []


def test_listen_returns_the_transcript_of_one_phrase(tmp_path: Path) -> None:
    devices = FakeDevices([speech()])
    result = call(voice_server(tmp_path, devices), "listen", {"silence_seconds": 0.5})
    assert not result.is_error
    assert "line0:" in str(result.structured_content)  # FakeRecognizer's final line
    assert devices.opened == 1


def test_listen_reports_silence_as_a_result_not_an_error(tmp_path: Path) -> None:
    devices = FakeDevices([[AudioChunk(pcm=bytes(3200))] * 200])
    result = call(voice_server(tmp_path, devices), "listen", {"max_seconds": 1.0})
    assert not result.is_error
    assert "no speech heard" in str(result.structured_content)


@pytest.mark.parametrize(
    "arguments", [{"max_seconds": 0.1}, {"max_seconds": 61}, {"silence_seconds": 9}]
)
def test_listen_rejects_out_of_range_durations_without_opening_the_microphone(
    tmp_path: Path, arguments: dict[str, float]
) -> None:
    devices = FakeDevices([speech()])
    result = call(voice_server(tmp_path, devices), "listen", arguments)
    assert result.is_error
    assert devices.opened == 0


def test_ask_speaks_the_question_before_it_listens(tmp_path: Path) -> None:
    order: list[str] = []

    class Ordered(FakeDevices):
        def play(self, audio: Any) -> None:
            order.append("play")
            super().play(audio)

        def listen_chunks(self) -> Any:
            order.append("listen")
            return super().listen_chunks()

    devices = Ordered([speech()])
    result = call(
        voice_server(tmp_path, devices), "ask", {"question": "أكمل؟", "silence_seconds": 0.5}
    )
    assert not result.is_error
    assert order == ["play", "listen"]


def test_a_failed_question_never_opens_the_microphone(tmp_path: Path) -> None:
    devices = FakeDevices([speech()])
    result = call(voice_server(tmp_path, devices), "ask", {"question": " "})
    assert result.is_error
    assert devices.opened == 0


def test_server_instructions_tell_agents_how_to_use_the_voice(tmp_path: Path) -> None:
    async def instructions(srv: Any) -> str:
        async with Client(srv) as client:
            return client.instructions or ""

    text = asyncio.run(instructions(voice_server(tmp_path, FakeDevices())))
    assert "announce" in text
    assert "Arabic" in text
    assert "announce" not in asyncio.run(instructions(server(tmp_path)))
