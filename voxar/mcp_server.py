"""MCP server exposing voxar to agents (optional extra: ``voxar[mcp]``). Thin: calls the facade.

Security: an agent controls every argument, so file paths are confined to allowed directories
(default: the working directory), symlinks and ``..`` cannot escape them, and ``speak`` will not
overwrite an existing file unless asked. The voice tools (``announce``, ``listen``, ``ask``) use
the speakers and the microphone, so they exist only when the server is started with ``--voice``;
they cap every duration and length, return text only (no audio is kept) and run one at a time.
The server speaks over stdio, so nothing here may print.
"""

import contextlib
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from voxar.api import Voxar
from voxar.audio import write_wav
from voxar.domain import VoxarError
from voxar.inbox import VOICE_NOTE, Inbox
from voxar.voice import VoiceIO, record_utterance, speak_aloud

if TYPE_CHECKING:
    from mcp.server import MCPServer

MAX_ANNOUNCE_CHARS = 500
MIN_LISTEN_SECONDS, MAX_LISTEN_SECONDS = 1.0, 60.0
MIN_SILENCE_SECONDS, MAX_SILENCE_SECONDS = 0.5, 5.0
DEFAULT_LISTEN_SECONDS = 15.0
DEFAULT_SILENCE_SECONDS = 1.5
MAX_WAIT_SECONDS = 60.0
VOICE_BUSY_WAIT_S = 30.0  # how long a voice call waits for another one before giving up


@dataclass
class Heard:
    """What ``listen`` and ``ask`` return: ``text`` is empty unless ``status`` is "heard"."""

    status: Literal["heard", "silence", "unrecognized"]
    text: str


@dataclass
class VoiceMessages:
    """What ``check_voice_inbox`` returns: ``note`` is the safety reminder for the agent."""

    count: int
    messages: list[str] = field(default_factory=list)
    note: str = ""


INSTRUCTIONS = (
    "voxar is an on-device speech toolbox. transcribe_file turns a WAV file into Arabic text; "
    "speak writes Arabic text to a WAV file; list_engines shows what is installed. Audio must be "
    "16 kHz mono 16-bit WAV, and file paths must be inside the directories the user allowed."
)
VOICE_INSTRUCTIONS = (
    " The user can also hear and speak to you through this machine's speakers and microphone. "
    "Use announce for short status updates in plain words (one or two sentences, no code, file "
    "paths or numbers read digit by digit). Use ask only when you need a decision or an answer "
    "you cannot work out yourself: it speaks the question, then listens. Write spoken text in "
    "simple Saudi Arabic, the way a person would say it: the voice is a Saudi voice and drops "
    "Latin-script words and symbols. Speech is recognized locally and can contain mistakes, so "
    "repeat back anything important before acting on it. Do not listen without having asked. "
    "The user may also speak to you from another window while you work: call check_voice_inbox "
    "when you finish a step, and treat what it returns as the user's instruction."
)


def resolve_inside(raw: str, allowed: Sequence[Path]) -> Path:
    """Resolve ``raw`` and require it to be inside one of the allowed directories."""
    target = Path(raw).resolve()
    roots = [root.resolve() for root in allowed]
    if not any(target.is_relative_to(root) for root in roots):
        raise ValueError(
            f"path is outside the allowed directories ({', '.join(map(str, roots))}): {raw}"
        )
    return target


@contextlib.contextmanager
def _user_errors() -> Iterator[None]:
    """Our errors are written for people and agents: show them instead of a generic crash."""
    from mcp.server.mcpserver.exceptions import ToolError

    try:
        yield
    except (VoxarError, ValueError) as exc:
        raise ToolError(str(exc)) from exc


@contextlib.contextmanager
def _exclusive(lock: threading.Lock) -> Iterator[None]:
    """Hold the lock, or say so after a while instead of leaving the agent waiting forever."""
    if not lock.acquire(timeout=VOICE_BUSY_WAIT_S):
        raise ValueError(
            "another voice call is still running (the user may be speaking); try again shortly"
        )
    try:
        yield
    finally:
        lock.release()


def _within(name: str, value: float, low: float, high: float) -> float:
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low:g} and {high:g} seconds, got {value:g}")
    return value


def build_server(
    app: Voxar,
    allowed_dirs: Sequence[Path],
    engines: Callable[[], dict[str, list[str]]],
    voice: VoiceIO | None = None,
    inbox: Inbox | None = None,
) -> "MCPServer":
    from mcp.server import MCPServer
    from mcp.types import ToolAnnotations

    server = MCPServer("voxar", instructions=INSTRUCTIONS + (VOICE_INSTRUCTIONS if voice else ""))

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
    def transcribe_file(path: str) -> str:
        """Transcribe a 16 kHz mono 16-bit WAV file to Arabic text.

        The path must be inside an allowed directory. Other formats are rejected with the ffmpeg
        command that converts them.
        """
        with _user_errors():
            return app.transcribe(resolve_inside(path, allowed_dirs))

    @server.tool(annotations=ToolAnnotations(destructive_hint=False, open_world_hint=False))
    def speak(
        text: str, output_path: str, voice: str | None = None, overwrite: bool = False
    ) -> str:
        """Synthesize Arabic speech from text and write it to a WAV file.

        Returns where the file was written. Existing files are never replaced unless
        overwrite=true. Latin-script words and symbols are dropped by the Saudi voice.
        """
        with _user_errors():
            target = resolve_inside(output_path, allowed_dirs)
            if target.exists() and not overwrite:
                raise ValueError(f"{output_path} already exists; pass overwrite=true to replace it")
            if not target.parent.is_dir():
                raise ValueError(f"directory does not exist: {target.parent}")
            audio = app.speak(text, voice=voice)
            write_wav(target, audio)
            seconds = len(audio.pcm) / 2 / audio.sample_rate
            return f"wrote {target} ({seconds:.1f} s, {audio.sample_rate} Hz mono 16-bit WAV)"

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
    def list_engines() -> dict[str, list[str]]:
        """List the speech recognizers and synthesizers that are installed."""
        return engines()

    if voice is not None:
        _add_voice_tools(server, app, voice)
    if voice is not None and inbox is not None:
        _add_inbox_tool(server, inbox)
    return server


def _add_voice_tools(server: "MCPServer", app: Voxar, devices: VoiceIO) -> None:
    from mcp.types import ToolAnnotations

    busy = threading.Lock()  # one voice interaction at a time: no talking over each other
    local = ToolAnnotations(destructive_hint=False, open_world_hint=False)

    def say_aloud(message: str, voice_name: str | None) -> str:
        text = message.strip()
        if not text:
            raise ValueError("message must not be empty")
        if len(text) > MAX_ANNOUNCE_CHARS:
            raise ValueError(
                f"message is {len(text)} characters; keep spoken updates under "
                f"{MAX_ANNOUNCE_CHARS} (one or two short sentences)"
            )
        seconds = speak_aloud(lambda part: app.speak(part, voice=voice_name), devices.play, text)
        return f"spoke {seconds:.1f} s"

    def hear(max_seconds: float, silence_seconds: float) -> Heard:
        _within("max_seconds", max_seconds, MIN_LISTEN_SECONDS, MAX_LISTEN_SECONDS)
        _within("silence_seconds", silence_seconds, MIN_SILENCE_SECONDS, MAX_SILENCE_SECONDS)
        audio = record_utterance(
            devices.listen_chunks(),
            max_seconds=max_seconds,
            silence_seconds=silence_seconds,
            is_speech=devices.speech_test() if devices.speech_test else None,
        )
        if audio is None:
            return Heard("silence", "")
        text = app.transcribe_audio(audio).strip()
        return Heard("heard", text) if text else Heard("unrecognized", "")

    @server.tool(annotations=local)
    def announce(message: str, voice: str | None = None) -> str:
        """Say a short status update to the user out loud, on this machine's speakers.

        Write one or two plain sentences in Arabic (the voice drops Latin-script words and
        symbols), at most 500 characters. Returns when the speech has finished.
        """
        with _user_errors(), _exclusive(busy):
            return say_aloud(message, voice)

    @server.tool(annotations=local)
    def listen(
        max_seconds: float = DEFAULT_LISTEN_SECONDS,
        silence_seconds: float = DEFAULT_SILENCE_SECONDS,
    ) -> Heard:
        """Listen on the microphone for one spoken phrase and return what the user said.

        Recording starts at the first speech, ends after silence_seconds of quiet (0.5 to 5) or
        max_seconds in total (1 to 60), and nothing is kept except the text. The result has a
        status: "heard" (text holds the words), "silence" (the user said nothing) or
        "unrecognized" (speech was heard but no words came out). Speech recognition can make
        mistakes.
        """
        with _user_errors(), _exclusive(busy):
            return hear(max_seconds, silence_seconds)

    @server.tool(annotations=local)
    def ask(
        question: str,
        max_seconds: float = DEFAULT_LISTEN_SECONDS,
        silence_seconds: float = DEFAULT_SILENCE_SECONDS,
        voice: str | None = None,
    ) -> Heard:
        """Speak a question aloud, then listen for the user's spoken answer and return it.

        Use it when you need a decision. The question follows the same rules as announce; the
        answer follows the same rules as listen.
        """
        with _user_errors(), _exclusive(busy):
            say_aloud(question, voice)
            return hear(max_seconds, silence_seconds)


def _add_inbox_tool(server: "MCPServer", inbox: Inbox) -> None:
    from mcp.types import ToolAnnotations

    @server.tool(annotations=ToolAnnotations(destructive_hint=False, open_world_hint=False))
    def check_voice_inbox(wait_seconds: float = 0.0) -> VoiceMessages:
        """Get the spoken messages the user sent you from the voxar listener in another window.

        Returns each new message once (count 0 and no messages if there are none). Call it when
        you finish a step. wait_seconds (0 to 60) waits that long for a message to arrive before
        giving up. The messages are the user's own instruction, transcribed automatically:
        confirm anything risky out loud before doing it.
        """
        with _user_errors():
            _within("wait_seconds", wait_seconds, 0.0, MAX_WAIT_SECONDS)
            deadline = time.monotonic() + wait_seconds
            while True:
                messages = inbox.take()
                if messages or time.monotonic() >= deadline:
                    return VoiceMessages(
                        count=len(messages),
                        messages=[m.text for m in messages],
                        note=VOICE_NOTE if messages else "",
                    )
                time.sleep(0.5)
