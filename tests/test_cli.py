import hashlib
import io
import wave
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.fakes import FakeRecognizer, FakeSynthesizer
from tests.test_audio import make_wav
from voxar.cli import main
from voxar.domain import AudioChunk
from voxar.models import ModelFile, ModelSpec
from voxar.registry import Registry


def registry() -> Registry:
    reg = Registry(discover=lambda _: {})
    reg.register_recognizer("moonshine", lambda _: FakeRecognizer())
    reg.register_synthesizer("fake", lambda _: FakeSynthesizer())
    return reg


def run(argv: list[str], tmp_path: Path, **env: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(
        argv,
        env={"HOME": str(tmp_path), **env},
        registry=registry(),
        stdout=out,
        stderr=err,
    )
    return code, out.getvalue(), err.getvalue()


def test_transcribe_prints_text(tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "a.wav", seconds=0.25)
    code, out, _ = run(["transcribe", str(wav)], tmp_path)
    assert code == 0
    # default chunking is 100 ms (3200 bytes): 0.25 s -> 3200 + 3200 + 1600
    assert out.strip() == "line0:3200 line1:3200 line2:1600"


def test_errors_are_reported_without_traceback(tmp_path: Path) -> None:
    code, out, err = run(["transcribe", str(tmp_path / "missing.wav")], tmp_path)
    assert code == 2
    assert out == ""
    assert err.startswith("error:")
    assert "Traceback" not in err


def test_say_writes_wav(tmp_path: Path) -> None:
    target = tmp_path / "hi.wav"
    code, _, _ = run(["say", "hello", "-o", str(target)], tmp_path, VOXAR_SYNTHESIZER="fake")
    assert code == 0
    with wave.open(str(target), "rb") as handle:
        assert handle.getnframes() == 160 * 5


def test_say_without_synthesizer_explains_how_to_fix(tmp_path: Path) -> None:
    code, _, err = run(["say", "hello", "-o", str(tmp_path / "x.wav")], tmp_path)
    assert code == 2
    assert "synthesizer" in err


def test_models_list_when_catalog_is_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("voxar.cli.CATALOG", {})
    code, out, _ = run(["models", "list"], tmp_path)
    assert code == 0
    assert "no models" in out.lower()


def test_doctor_reports_environment(tmp_path: Path) -> None:
    code, out, _ = run(["doctor"], tmp_path)
    assert code == 0
    for expected in ("python", "cache", "recognizers", "moonshine"):
        assert expected in out.lower()


def test_no_command_prints_help_and_fails(tmp_path: Path) -> None:
    code, _, err = run([], tmp_path)
    assert code == 2
    assert "usage" in err.lower()


def test_version_flag(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as info:
        main(["--version"], env={"HOME": str(tmp_path)}, stdout=io.StringIO(), stderr=io.StringIO())
    assert info.value.code == 0


def _spec() -> ModelSpec:
    return ModelSpec(
        id="demo",
        revision="r1",
        license="MIT",
        source="https://example.invalid",
        files=(ModelFile(name="w.bin", sha256=hashlib.sha256(b"x").hexdigest()),),
    )


def test_models_list_shows_catalog_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("voxar.cli.CATALOG", {"demo": _spec()})
    code, out, _ = run(["models", "list"], tmp_path)
    assert code == 0
    assert "demo  r1  MIT" in out


def test_models_verify_unknown_name(tmp_path: Path) -> None:
    code, _, err = run(["models", "verify", "nope"], tmp_path)
    assert code == 2
    assert "unknown model" in err


def test_models_verify_not_installed_explains_next_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("voxar.cli.CATALOG", {"demo": _spec()})
    code, _, err = run(["models", "verify", "demo"], tmp_path)
    assert code == 2
    assert "voxar models pull" in err


def test_models_verify_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("voxar.cli.CATALOG", {"demo": _spec()})
    target = tmp_path / ".cache" / "voxar" / "demo" / "r1"
    target.mkdir(parents=True)
    (target / "w.bin").write_bytes(b"x")
    code, out, _ = run(["models", "verify", "demo"], tmp_path)
    assert code == 0
    assert "demo: ok" in out


class _FakeFetcher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, spec: ModelSpec) -> "Callable[[ModelFile], list[bytes]]":
        def fetch(model_file: ModelFile) -> list[bytes]:
            self.calls.append(model_file.name)
            return [b"x"]

        return fetch


def run_with(argv: list[str], tmp_path: Path, **kwargs: Any) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(
        argv, env={"HOME": str(tmp_path)}, registry=registry(), stdout=out, stderr=err, **kwargs
    )
    return code, out.getvalue(), err.getvalue()


def test_models_pull_downloads_verifies_and_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("voxar.cli.CATALOG", {"demo": _spec()})
    fetcher = _FakeFetcher()
    code, out, _ = run_with(
        ["models", "pull", "demo", "--accept-license"], tmp_path, fetcher_for=fetcher
    )
    assert code == 0
    assert fetcher.calls == ["w.bin"]
    assert "demo: installed" in out


def test_models_pull_requires_license_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("voxar.cli.CATALOG", {"demo": _spec()})
    fetcher = _FakeFetcher()
    code, _, err = run_with(["models", "pull", "demo"], tmp_path, fetcher_for=fetcher)
    assert code == 2
    assert "--accept-license" in err
    assert fetcher.calls == []


def test_models_pull_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("voxar.cli.CATALOG", {"demo": _spec()})
    target = tmp_path / ".cache" / "voxar" / "demo" / "r1"
    target.mkdir(parents=True)
    (target / "w.bin").write_bytes(b"x")
    fetcher = _FakeFetcher()
    code, out, _ = run_with(
        ["models", "pull", "demo", "--accept-license"], tmp_path, fetcher_for=fetcher
    )
    assert code == 0
    assert fetcher.calls == []
    assert "already installed" in out


def test_models_pull_unknown_model(tmp_path: Path) -> None:
    code, _, err = run_with(["models", "pull", "nope", "--accept-license"], tmp_path)
    assert code == 2
    assert "unknown model" in err


def test_listen_prints_partials_and_finals(tmp_path: Path) -> None:
    chunks = [AudioChunk(pcm=bytes(4))] * 2
    code, out, _ = run_with(["listen"], tmp_path, mic=lambda: iter(chunks))
    assert code == 0
    assert "line0:4" in out and "line1:4" in out


def test_listen_stops_cleanly_on_ctrl_c(tmp_path: Path) -> None:
    def interrupted() -> "Iterator[AudioChunk]":
        raise KeyboardInterrupt
        yield  # pragma: no cover

    code, _, err = run_with(["listen"], tmp_path, mic=interrupted)
    assert code == 0
    assert "Traceback" not in err


def test_models_list_includes_the_real_moonshine_model(tmp_path: Path) -> None:
    code, out, _ = run(["models", "list"], tmp_path)
    assert code == 0
    assert "moonshine-tiny-streaming-ar" in out


def test_mcp_command_serves_with_allowed_dirs(tmp_path: Path) -> None:
    seen: dict[str, Any] = {}

    def fake_serve(
        app: Any, allowed: Any, engines: Any, voice: bool, inbox_dir: Path, config: Any
    ) -> None:
        seen["allowed"] = list(allowed)
        seen["engines"] = engines()
        seen["voice"] = voice

    code, _, _ = run_with(
        ["mcp", "--allow-dir", str(tmp_path / "a"), "--allow-dir", str(tmp_path / "b")],
        tmp_path,
        serve_mcp=fake_serve,
    )
    assert code == 0
    assert seen["allowed"] == [tmp_path / "a", tmp_path / "b"]
    assert "moonshine" in seen["engines"]["recognizers"]
    assert seen["voice"] is False  # the microphone and speakers are opt-in


def test_mcp_command_defaults_to_the_working_directory(tmp_path: Path) -> None:
    seen: dict[str, Any] = {}
    code, _, _ = run_with(
        ["mcp"],
        tmp_path,
        serve_mcp=lambda app, allowed, engines, voice, inbox_dir, config: seen.update(
            allowed=list(allowed)
        ),
    )
    assert code == 0
    assert seen["allowed"] == [Path.cwd()]


def test_mcp_voice_flag_enables_the_voice_tools(tmp_path: Path) -> None:
    seen: dict[str, Any] = {}
    code, _, _ = run_with(
        ["mcp", "--voice"],
        tmp_path,
        serve_mcp=lambda app, allowed, engines, voice, inbox_dir, config: seen.update(
            voice=voice, inbox_dir=inbox_dir
        ),
    )
    assert code == 0
    assert seen == {"voice": True, "inbox_dir": tmp_path / ".cache" / "voxar" / "inbox"}


@pytest.mark.parametrize(("flags", "warmed"), [(["--voice"], True), ([], False)])
def test_only_the_voice_server_loads_its_engines_at_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flags: list[str], warmed: bool
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr("voxar.cli._warm_in_background", calls.append)
    code, _, _ = run_with(["mcp", *flags], tmp_path, serve_mcp=lambda *args: None)
    assert code == 0
    assert bool(calls) is warmed  # the first spoken update should not wait for the voice to load


def test_say_without_an_output_file_plays_on_the_speakers(tmp_path: Path) -> None:
    played: list[Any] = []
    out, err = io.StringIO(), io.StringIO()
    code = main(
        ["say", "abc"],
        env={"HOME": str(tmp_path), "VOXAR_SYNTHESIZER": "fake"},
        registry=registry(),
        play=played.append,
        stdout=out,
        stderr=err,
    )
    assert code == 0
    assert len(played) == 1
    assert len(played[0].pcm) == 160 * 3 * 2  # FakeSynthesizer: 160 samples per character
    assert out.getvalue() == ""


def test_mcp_command_without_the_extra_gives_an_install_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    monkeypatch.setitem(sys.modules, "mcp", None)
    monkeypatch.setitem(sys.modules, "mcp.server", None)
    code, _, err = run_with(["mcp"], tmp_path)
    assert code == 2
    assert "voxar[mcp]" in err


def test_serve_defaults_to_loopback(tmp_path: Path) -> None:
    seen: dict[str, Any] = {}

    def fake_serve(
        app: Any, engines: Any, host: str, port: int, allow_remote: bool, warm: bool, token: Any
    ) -> None:
        seen.update(host=host, port=port, allow_remote=allow_remote, warm=warm, token=token)

    code, _, _ = run_with(["serve"], tmp_path, serve_http=fake_serve)
    assert code == 0
    assert seen == {
        "host": "127.0.0.1",
        "port": 8765,
        "allow_remote": False,
        "warm": True,
        "token": None,  # loopback needs no token
    }


def test_serve_refuses_a_public_address_without_allow_remote(tmp_path: Path) -> None:
    seen: list[str] = []
    code, _, err = run_with(
        ["serve", "--host", "0.0.0.0"],
        tmp_path,
        serve_http=lambda *a: seen.append("started"),
    )
    assert code == 2
    assert "--allow-remote" in err
    assert seen == []


def test_serve_allows_a_public_address_when_explicit(tmp_path: Path) -> None:
    seen: dict[str, Any] = {}
    code, _, _ = run_with(
        ["serve", "--host", "0.0.0.0", "--port", "9000", "--allow-remote"],
        tmp_path,
        serve_http=lambda app, engines, host, port, remote, warm, token: seen.update(
            host=host, remote=remote, token=token
        ),
    )
    assert code == 0
    assert seen["host"] == "0.0.0.0" and seen["remote"] is True
    assert len(seen["token"]) >= 32  # exposing the server always comes with a random token


def test_every_exposed_start_gets_a_new_token_and_prints_the_link(tmp_path: Path) -> None:
    tokens: list[str] = []

    def record(*args: Any) -> None:
        tokens.append(args[-1])

    for _ in range(2):
        run_with(["serve", "--host", "0.0.0.0", "--allow-remote"], tmp_path, serve_http=record)
    assert tokens[0] != tokens[1]


def test_serve_without_the_extra_gives_an_install_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    monkeypatch.setitem(sys.modules, "uvicorn", None)
    code, _, err = run_with(["serve"], tmp_path)
    assert code == 2
    assert "voxar[server]" in err


def test_background_warm_up_reports_but_never_raises(capsys: pytest.CaptureFixture[str]) -> None:
    from voxar.cli import _warm_in_background

    class Broken:
        def warm_up(self) -> None:
            raise RuntimeError("model file is corrupt")

    _warm_in_background(Broken()).join(timeout=5)  # type: ignore[arg-type]
    assert "warm-up skipped" in capsys.readouterr().err


def test_no_warm_flag_is_passed_to_the_server(tmp_path: Path) -> None:
    seen: dict[str, Any] = {}
    code, _, _ = run_with(
        ["serve", "--no-warm"],
        tmp_path,
        serve_http=lambda app, engines, host, port, remote, warm, token: seen.update(warm=warm),
    )
    assert code == 0
    assert seen == {"warm": False}


# --- voxar inbox: spoken messages for a running agent ---


def _speech_chunks() -> "Iterator[AudioChunk]":
    import struct

    loud = AudioChunk(pcm=struct.pack("<h", 3000) * 1600)
    quiet = AudioChunk(pcm=bytes(3200))
    yield from [loud] * 3 + [quiet] * 20


def _inbox_run(
    argv: list[str], tmp_path: Path, stdin: str = "", **kwargs: Any
) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(
        argv,
        env={"HOME": str(tmp_path)},
        registry=registry(),
        stdin=io.StringIO(stdin),
        stdout=out,
        stderr=err,
        **kwargs,
    )
    return code, out.getvalue(), err.getvalue()


def _messages(tmp_path: Path) -> list[str]:
    from voxar.inbox import Inbox

    return [m.text for m in Inbox(tmp_path / ".cache" / "voxar" / "inbox").take()]


def test_inbox_listen_waits_for_enter_and_stores_what_was_said(tmp_path: Path) -> None:
    code, out, err = _inbox_run(
        ["inbox", "listen", "--once", "--silence", "0.5"], tmp_path, stdin="\n", mic=_speech_chunks
    )
    assert code == 0
    assert out.startswith("heard: line0:")
    assert "press Enter" in err
    assert len(_messages(tmp_path)) == 1


def test_inbox_listen_stops_when_the_input_ends(tmp_path: Path) -> None:
    code, out, _ = _inbox_run(["inbox", "listen"], tmp_path, stdin="", mic=_speech_chunks)
    assert (code, out) == (0, "")
    assert _messages(tmp_path) == []


def test_always_on_warns_that_everything_it_hears_counts(tmp_path: Path) -> None:
    code, _, err = _inbox_run(
        ["inbox", "listen", "--always-on", "--once", "--silence", "0.5"],
        tmp_path,
        mic=_speech_chunks,
    )
    assert code == 0
    assert "everything the microphone hears" in err
    assert "--wake" in err
    assert len(_messages(tmp_path)) == 1


def test_a_wake_word_filters_phrases_that_lack_it(tmp_path: Path) -> None:
    code, out, _ = _inbox_run(
        ["inbox", "listen", "--wake", "فوكسار", "--silence", "0.5"],
        tmp_path,
        stdin="\n",
        mic=_speech_chunks,
    )
    assert (code, out) == (0, "")  # FakeRecognizer never says the wake word
    assert _messages(tmp_path) == []


def test_inbox_read_prints_each_message_once(tmp_path: Path) -> None:
    from voxar.inbox import Inbox

    Inbox(tmp_path / ".cache" / "voxar" / "inbox").add("اعمل الاختبارات")
    assert _inbox_run(["inbox", "read"], tmp_path)[1] == "اعمل الاختبارات\n"
    assert _inbox_run(["inbox", "read"], tmp_path)[1] == ""


def test_inbox_read_hook_blocks_the_stop_with_the_message_as_the_reason(tmp_path: Path) -> None:
    import json

    from voxar.inbox import Inbox

    Inbox(tmp_path / ".cache" / "voxar" / "inbox").add("اعمل الاختبارات")
    _, out, _ = _inbox_run(["inbox", "read", "--hook"], tmp_path)
    decision = json.loads(out)
    assert decision["decision"] == "block"
    assert "اعمل الاختبارات" in decision["reason"]
    assert _inbox_run(["inbox", "read", "--hook"], tmp_path)[1] == ""  # nothing left: no output


def test_inbox_clear_deletes_messages(tmp_path: Path) -> None:
    from voxar.inbox import Inbox

    Inbox(tmp_path / ".cache" / "voxar" / "inbox").add("x")
    assert _inbox_run(["inbox", "clear"], tmp_path)[0] == 0
    assert _messages(tmp_path) == []
