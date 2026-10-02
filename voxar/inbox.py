"""A tiny on-disk inbox for spoken messages: one process writes them, others read them once.

``voxar inbox listen`` (a separate window) appends what the user says; the MCP server and the
Claude Code hook read it. Standard library only. The file lives in the cache directory, so every
process must see the same ``VOXAR_CACHE_DIR``.
"""

import contextlib
import json
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from voxar.domain import VoxarError

MAX_MESSAGE_CHARS = 2000
_LOCK_WAIT_S = 2.0
_STALE_LOCK_S = 10.0
_COMPACT_BYTES = 1 << 20


@dataclass(frozen=True)
class Message:
    id: int
    time: str
    text: str


class Inbox:
    """Append-only JSON lines plus a read offset; ``take`` returns each message exactly once."""

    def __init__(self, directory: Path) -> None:
        self._dir = directory
        self._log = directory / "inbox.jsonl"
        self._offset = directory / "inbox.offset"
        self._lock = directory / "inbox.lock"

    def add(self, text: str) -> Message:
        body = text.strip()
        if not body:
            raise ValueError("a spoken message must not be empty")
        body = body[:MAX_MESSAGE_CHARS]
        with self._locked():
            number = self._count() + 1
            message = Message(
                number, datetime.now(timezone.utc).isoformat(timespec="seconds"), body
            )
            line = json.dumps(message.__dict__, ensure_ascii=False) + "\n"
            with self._log.open("a", encoding="utf-8") as handle:
                handle.write(line)
        return message

    def take(self) -> list[Message]:
        """Return the unread messages, oldest first, and mark them read."""
        with self._locked():
            if not self._log.exists():
                return []
            data = self._log.read_bytes()
            start = min(self._read_offset(), len(data))
            fresh = [_parse(line) for line in data[start:].decode("utf-8").splitlines() if line]
            self._write_offset(len(data))
            if len(data) > _COMPACT_BYTES:
                self._log.write_bytes(b"")
                self._write_offset(0)
            return [m for m in fresh if m is not None]

    def pending(self) -> int:
        """How many messages are unread, without reading them."""
        with self._locked():
            if not self._log.exists():
                return 0
            data = self._log.read_bytes()
            return sum(
                1 for line in data[min(self._read_offset(), len(data)) :].splitlines() if line
            )

    def clear(self) -> None:
        with self._locked():
            for path in (self._log, self._offset):
                path.unlink(missing_ok=True)

    def _count(self) -> int:
        if not self._log.exists():
            return 0
        lines = self._log.read_text(encoding="utf-8").splitlines()
        last = _parse(lines[-1]) if lines else None
        return last.id if last else len(lines)

    def _read_offset(self) -> int:
        try:
            return int(self._offset.read_text(encoding="utf-8").strip() or 0)
        except (OSError, ValueError):
            return 0

    def _write_offset(self, value: int) -> None:
        temporary = self._offset.with_suffix(".tmp")
        temporary.write_text(str(value), encoding="utf-8")
        os.replace(temporary, self._offset)

    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        self._dir.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + _LOCK_WAIT_S
        while True:
            try:
                os.close(os.open(self._lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                break
            except FileExistsError:
                with contextlib.suppress(OSError):
                    if time.time() - self._lock.stat().st_mtime > _STALE_LOCK_S:
                        self._lock.unlink()  # a crashed process left it behind
                        continue
                if time.monotonic() > deadline:
                    raise VoxarError(
                        f"the inbox is busy: remove {self._lock} if no voxar is running"
                    ) from None
                time.sleep(0.02)
        try:
            yield
        finally:
            with contextlib.suppress(OSError):
                self._lock.unlink()


def _parse(line: str) -> Message | None:
    try:
        data = json.loads(line)
        return Message(int(data["id"]), str(data["time"]), str(data["text"]))
    except (ValueError, KeyError, TypeError):
        return None  # a torn or foreign line is skipped, never fatal


def describe(messages: list[Message]) -> str:
    """The text an agent receives: numbered, with a reminder that speech can be misheard."""
    if not messages:
        return "(no new voice messages)"
    lines = [f"{i}. {m.text}" for i, m in enumerate(messages, 1)]
    return (
        "The user said, by voice (transcribed automatically, so words may be wrong; confirm "
        "anything risky out loud before doing it):\n" + "\n".join(lines)
    )
