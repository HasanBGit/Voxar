"""The spoken-message inbox: each message is delivered exactly once, across processes."""

import os
import threading
from pathlib import Path

import pytest

import voxar.inbox as inbox_module
from voxar.domain import VoxarError
from voxar.inbox import MAX_MESSAGE_CHARS, Inbox, describe


def test_a_message_is_delivered_once_in_order(tmp_path: Path) -> None:
    inbox = Inbox(tmp_path)
    inbox.add("أول رسالة")
    inbox.add("ثاني رسالة")
    assert [m.text for m in inbox.take()] == ["أول رسالة", "ثاني رسالة"]
    assert inbox.take() == []
    inbox.add("ثالثة")
    assert [m.id for m in inbox.take()] == [3]


def test_two_readers_never_see_the_same_message(tmp_path: Path) -> None:
    writer, first, second = Inbox(tmp_path), Inbox(tmp_path), Inbox(tmp_path)
    writer.add("مرحبا")
    assert [m.text for m in first.take()] == ["مرحبا"]
    assert second.take() == []


def test_pending_counts_without_consuming(tmp_path: Path) -> None:
    inbox = Inbox(tmp_path)
    assert inbox.pending() == 0
    inbox.add("a")
    inbox.add("b")
    assert inbox.pending() == 2
    assert len(inbox.take()) == 2
    assert inbox.pending() == 0


def test_empty_messages_are_refused_and_long_ones_cut(tmp_path: Path) -> None:
    inbox = Inbox(tmp_path)
    with pytest.raises(ValueError, match="empty"):
        inbox.add("   ")
    assert len(inbox.add("x" * (MAX_MESSAGE_CHARS + 50)).text) == MAX_MESSAGE_CHARS


def test_clear_removes_everything(tmp_path: Path) -> None:
    inbox = Inbox(tmp_path)
    inbox.add("a")
    inbox.clear()
    assert inbox.take() == []
    inbox.add("b")
    assert [m.id for m in inbox.take()] == [1]


def test_a_torn_line_is_skipped_not_fatal(tmp_path: Path) -> None:
    inbox = Inbox(tmp_path)
    inbox.add("سليم")
    with (tmp_path / "inbox.jsonl").open("a", encoding="utf-8") as handle:
        handle.write('{"id": 2, "time": "x", "te\n')
    assert [m.text for m in inbox.take()] == ["سليم"]


def test_concurrent_writers_lose_no_messages(tmp_path: Path) -> None:
    inbox = Inbox(tmp_path)
    threads = [threading.Thread(target=inbox.add, args=(f"m{n}",)) for n in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    messages = inbox.take()
    assert sorted(m.text for m in messages) == sorted(f"m{n}" for n in range(20))
    assert len({m.id for m in messages}) == 20


def test_a_crashed_process_lock_is_recovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(inbox_module, "_STALE_LOCK_S", 0.0)
    (tmp_path / "inbox.lock").write_text("", encoding="utf-8")
    Inbox(tmp_path).add("still works")


def test_a_held_lock_gives_a_clear_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(inbox_module, "_LOCK_WAIT_S", 0.1)
    (tmp_path / "inbox.lock").write_text("", encoding="utf-8")
    with pytest.raises(VoxarError, match="inbox is busy"):
        Inbox(tmp_path).add("x")


def test_a_large_log_is_emptied_once_everything_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(inbox_module, "_COMPACT_BYTES", 10)
    inbox = Inbox(tmp_path)
    inbox.add("a long enough message to pass ten bytes")
    assert len(inbox.take()) == 1
    assert (tmp_path / "inbox.jsonl").read_bytes() == b""
    inbox.add("next")
    assert [m.text for m in inbox.take()] == ["next"]


def test_describe_numbers_messages_and_warns_about_mistakes() -> None:
    assert describe([]) == "(no new voice messages)"
    text = describe([inbox_module.Message(1, "t", "اعمل الاختبارات")])
    assert "1. اعمل الاختبارات" in text
    assert "words may be wrong" in text


def test_windows_style_permission_errors_on_the_lock_are_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On Windows, creating a lock file another process is deleting raises PermissionError."""
    real_open = os.open
    calls = {"denied": 0}

    def flaky_open(path: str | os.PathLike[str], flags: int, mode: int = 0o777) -> int:
        if str(path).endswith("inbox.lock") and calls["denied"] < 3:
            calls["denied"] += 1
            raise PermissionError(13, "Permission denied")
        return real_open(path, flags, mode)

    monkeypatch.setattr("voxar.inbox.os.open", flaky_open)
    assert Inbox(tmp_path).add("حصلت بعد المحاولة").id == 1
    assert calls["denied"] == 3
