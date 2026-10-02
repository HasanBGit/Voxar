"""Streaming HTTPS downloads for model files. The only module that touches the network."""

import urllib.error
import urllib.request
from collections.abc import Iterator
from http.client import HTTPMessage
from typing import IO, Any

from voxar import __version__
from voxar.domain import ConfigError, DownloadError
from voxar.models import Fetcher, ModelFile, ModelSpec

_BLOCK = 1 << 20
_TIMEOUT_S = 30.0


class _HttpsOnlyRedirects(urllib.request.HTTPRedirectHandler):
    """Hugging Face and others redirect large files to a CDN; never follow a downgrade."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        if not newurl.startswith("https://"):
            raise DownloadError(f"refusing redirect to a non-https URL: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(request: urllib.request.Request, timeout: float) -> Any:
    return urllib.request.build_opener(_HttpsOnlyRedirects).open(request, timeout=timeout)


def fetcher_for(spec: ModelSpec) -> Fetcher:
    """Return a fetcher that downloads ``<spec.source>/<file name>`` over HTTPS."""

    def fetch(model_file: ModelFile) -> Iterator[bytes]:
        url = f"{spec.source.rstrip('/')}/{model_file.name}"
        if not url.startswith("https://"):
            raise ConfigError(f"model downloads must use https, got {url!r}")
        # the scheme is validated as https above, so S310 (arbitrary schemes) cannot apply
        agent = {"User-Agent": f"voxar/{__version__}"}
        request = urllib.request.Request(url, headers=agent)  # noqa: S310
        try:
            with _open(request, _TIMEOUT_S) as response:
                while block := response.read(_BLOCK):
                    yield block
        except (urllib.error.URLError, TimeoutError) as exc:
            raise DownloadError(f"could not download {model_file.name} from {url}: {exc}") from exc

    return fetch
