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

    def fake_serve(app: Any, allowed: Any, engines: Any) -> None:
        seen["allowed"] = list(allowed)
        seen["engines"] = engines()

    code, _, _ = run_with(
        ["mcp", "--allow-dir", str(tmp_path / "a"), "--allow-dir", str(tmp_path / "b")],
        tmp_path,
        serve_mcp=fake_serve,
    )
    assert code == 0
    assert seen["allowed"] == [tmp_path / "a", tmp_path / "b"]
    assert "moonshine" in seen["engines"]["recognizers"]


def test_mcp_command_defaults_to_the_working_directory(tmp_path: Path) -> None:
    seen: dict[str, Any] = {}
    code, _, _ = run_with(
        ["mcp"],
        tmp_path,
        serve_mcp=lambda app, allowed, engines: seen.update(allowed=list(allowed)),
    )
    assert code == 0
    assert seen["allowed"] == [Path.cwd()]


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
        app: Any, engines: Any, host: str, port: int, allow_remote: bool, warm: bool
    ) -> None:
        seen.update(host=host, port=port, allow_remote=allow_remote, warm=warm)

    code, _, _ = run_with(["serve"], tmp_path, serve_http=fake_serve)
    assert code == 0
    assert seen == {"host": "127.0.0.1", "port": 8765, "allow_remote": False, "warm": True}


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
        serve_http=lambda app, engines, host, port, remote, warm: seen.update(
            host=host, remote=remote
        ),
    )
    assert code == 0
    assert seen == {"host": "0.0.0.0", "remote": True}


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
        serve_http=lambda app, engines, host, port, remote, warm: seen.update(warm=warm),
    )
    assert code == 0
    assert seen == {"warm": False}
