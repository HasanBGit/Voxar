import io
import urllib.error
import urllib.request
from http.client import HTTPMessage
from typing import Any

import pytest

from voxar.domain import ConfigError, DownloadError
from voxar.models import ModelFile, ModelSpec
from voxar.net import _HttpsOnlyRedirects, fetcher_for

SHA = "0" * 64


def spec(source: str) -> ModelSpec:
    return ModelSpec(
        id="m", revision="r", license="MIT", source=source, files=(ModelFile("a.bin", SHA),)
    )


class FakeResponse(io.BytesIO):
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def test_streams_the_file_in_blocks_from_source_slash_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    def fake_open(request: Any, timeout: float) -> FakeResponse:
        seen["url"] = request.full_url
        seen["agent"] = request.get_header("User-agent")
        seen["timeout"] = timeout
        return FakeResponse(b"x" * (2 * 1024 * 1024 + 5))

    monkeypatch.setattr("voxar.net._open", fake_open)
    blocks = list(fetcher_for(spec("https://example.test/model/"))(ModelFile("a.bin", SHA)))
    assert seen["url"] == "https://example.test/model/a.bin"
    assert seen["agent"].startswith("voxar/")
    assert seen["timeout"] > 0
    assert sum(len(b) for b in blocks) == 2 * 1024 * 1024 + 5
    assert len(blocks) == 3


@pytest.mark.parametrize("url", ["http://example.test/m", "file:///etc/passwd", "ftp://x/m"])
def test_only_https_is_allowed(url: str) -> None:
    with pytest.raises(ConfigError, match="https"):
        list(fetcher_for(spec(url))(ModelFile("a.bin", SHA)))


def test_network_errors_become_download_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(request: Any, timeout: float) -> FakeResponse:
        raise urllib.error.URLError("no route")

    monkeypatch.setattr("voxar.net._open", boom)
    with pytest.raises(DownloadError, match="a.bin"):
        list(fetcher_for(spec("https://example.test/m"))(ModelFile("a.bin", SHA)))


def test_redirect_to_plain_http_is_refused() -> None:
    handler = _HttpsOnlyRedirects()
    request = urllib.request.Request("https://example.test/a")
    with pytest.raises(DownloadError, match="non-https"):
        handler.redirect_request(
            request, io.BytesIO(), 302, "Found", HTTPMessage(), "http://evil.test/a"
        )


def test_redirect_to_https_is_followed() -> None:
    handler = _HttpsOnlyRedirects()
    request = urllib.request.Request("https://example.test/a")
    followed = handler.redirect_request(
        request, io.BytesIO(), 302, "Found", HTTPMessage(), "https://cdn.test/a"
    )
    assert followed is not None
    assert followed.full_url == "https://cdn.test/a"
