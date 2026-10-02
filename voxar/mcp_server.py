"""MCP server exposing voxar to agents (optional extra: ``voxar[mcp]``). Thin: calls the facade.

Security: an agent controls every argument, so file paths are confined to allowed directories
(default: the working directory), symlinks and ``..`` cannot escape them, and ``speak`` will not
overwrite an existing file unless asked. The server speaks over stdio, so nothing here may print.
"""

import contextlib
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from voxar.api import Voxar
from voxar.audio import write_wav
from voxar.domain import VoxarError

if TYPE_CHECKING:
    from mcp.server import MCPServer


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


def build_server(
    app: Voxar,
    allowed_dirs: Sequence[Path],
    engines: Callable[[], dict[str, list[str]]],
) -> "MCPServer":
    from mcp.server import MCPServer

    server = MCPServer("voxar")

    @server.tool()
    def transcribe_file(path: str) -> str:
        """Transcribe a 16 kHz mono 16-bit WAV file to text (Arabic)."""
        with _user_errors():
            return app.transcribe(resolve_inside(path, allowed_dirs))

    @server.tool()
    def speak(
        text: str, output_path: str, voice: str | None = None, overwrite: bool = False
    ) -> str:
        """Synthesize speech from text and write it to a WAV file; returns where it was written."""
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

    @server.tool()
    def list_engines() -> dict[str, list[str]]:
        """List the speech recognizers and synthesizers that are installed."""
        return engines()

    return server
