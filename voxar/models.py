"""Model cache with pinned revisions and SHA-256 verification.

Nothing is trusted until its hash matches the catalog. Downloads go to a temporary file that is
verified before it is moved into place, so a bad or interrupted download never looks installed.
The network fetcher is injected: this module does no network I/O itself.
"""

import hashlib
import os
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from voxar.domain import (
    ConfigError,
    LicenseNotAcceptedError,
    ModelIntegrityError,
    ModelNotFoundError,
    OfflineModeError,
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_UNSAFE = {"", ".", ".."}


def _check_component(value: str, what: str) -> None:
    if value in _UNSAFE or any(c in value for c in ("/", "\\", "\x00")):
        raise ConfigError(f"invalid {what}: {value!r}")


@dataclass(frozen=True)
class ModelFile:
    name: str
    sha256: str

    def __post_init__(self) -> None:
        _check_component(self.name, "model file name")
        if not _SHA256.fullmatch(self.sha256):
            raise ConfigError(f"sha256 must be 64 lowercase hex characters: {self.sha256!r}")


@dataclass(frozen=True)
class ModelSpec:
    id: str
    revision: str
    license: str
    source: str
    files: tuple[ModelFile, ...]

    def __post_init__(self) -> None:
        _check_component(self.id, "model id")
        _check_component(self.revision, "model revision")


Fetcher = Callable[[ModelFile], Iterable[bytes]]


class ModelStore:
    def __init__(self, cache_dir: Path, *, offline: bool = False) -> None:
        self._cache_dir = cache_dir
        self._offline = offline

    def path(self, spec: ModelSpec) -> Path:
        return self._cache_dir / spec.id / spec.revision

    def is_installed(self, spec: ModelSpec) -> bool:
        return all((self.path(spec) / f.name).is_file() for f in spec.files)

    def verify(self, spec: ModelSpec) -> None:
        for model_file in spec.files:
            target = self.path(spec) / model_file.name
            if not target.is_file():
                raise ModelNotFoundError(
                    f"model {spec.id}@{spec.revision} is not installed. "
                    f"Run: voxar models pull {spec.id}"
                )
            actual = _sha256_of(target)
            if actual != model_file.sha256:
                raise ModelIntegrityError(
                    f"{model_file.name}: sha256 mismatch "
                    f"(expected {model_file.sha256}, got {actual})"
                )

    def install(self, spec: ModelSpec, fetch: Fetcher, *, accept_license: bool) -> Path:
        if self._offline:
            raise OfflineModeError("offline mode is on (VOXAR_OFFLINE); cannot download models")
        if not accept_license:
            raise LicenseNotAcceptedError(
                f"{spec.id} is licensed under {spec.license}; review {spec.source} "
                "and re-run with --accept-license"
            )
        target = self.path(spec)
        target.mkdir(parents=True, exist_ok=True)
        for model_file in spec.files:
            self._download(model_file, fetch, target)
        return target

    @staticmethod
    def _download(model_file: ModelFile, fetch: Fetcher, target: Path) -> None:
        partial = target / f".{model_file.name}.part"
        digest = hashlib.sha256()
        try:
            with partial.open("wb") as handle:
                for block in fetch(model_file):
                    digest.update(block)
                    handle.write(block)
            if digest.hexdigest() != model_file.sha256:
                raise ModelIntegrityError(
                    f"{model_file.name}: sha256 mismatch (expected {model_file.sha256}, "
                    f"got {digest.hexdigest()})"
                )
            os.replace(partial, target / model_file.name)
        finally:
            partial.unlink(missing_ok=True)


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# Models voxar knows how to install. SHA-256 values are measured from the real files, never guessed.
_MOONSHINE_AR = "https://download.moonshine.ai/model/tiny-streaming-ar/quantized_26_08_24"
_MOONSHINE_AR_LICENSE = (
    "MIT per upstream LICENSE (unconfirmed for this artifact, see THIRD_PARTY_LICENSES.md)"
)

# Pinned to an exact Hugging Face commit; LFS hashes are the ones Hugging Face reports and are
# re-verified on every download. Weights are loaded with torch.load(weights_only=True) only.
_NABRA = "https://huggingface.co/oddadmix/Nabra-Saudi-7M/resolve/ef45d882f20355767190dffb2a34393ed1df74fa"

CATALOG: Mapping[str, ModelSpec] = {
    "nabra-saudi-7m": ModelSpec(
        id="nabra-saudi-7m",
        revision="ef45d882f20355767190dffb2a34393ed1df74fa",
        license="Apache-2.0 (model weights); the TTS plugin that runs it is GPL-3.0",
        source=_NABRA,
        files=(
            ModelFile(
                "nabra_saudi_7m.pth",
                "98531f832d224bcecd89e1d582db7c22e034b706bd936e33b2f1c56a99c57a9f",
            ),
            ModelFile(
                "af_msa.pt", "9324145629d870a899078ef0a70eabc0706c219ccbf002fa6a18278a201c9664"
            ),
            ModelFile(
                "config.json", "4e203206481813c0d3cb9e1b8c308d54c10f9e416dd6931036deb2c7e03b241e"
            ),
        ),
    ),
    "moonshine-tiny-streaming-ar": ModelSpec(
        id="moonshine-tiny-streaming-ar",
        revision="quantized_26_08_24",
        # Upstream LICENSE and the Hugging Face card say MIT for streaming models; Moonshine's own
        # downloader prints a generic non-commercial notice for every non-English model.
        # Unresolved: see THIRD_PARTY_LICENSES.md before any commercial use.
        license=_MOONSHINE_AR_LICENSE,
        source=_MOONSHINE_AR,
        files=(
            ModelFile(
                "adapter.ort", "9c1278a338b4ff268fc5741be01446d56ca9cba9ff5f4a75c5e1b2c2e2739361"
            ),
            ModelFile(
                "cross_kv.ort", "e317af289233894f49da429d4561150c2f61ca86c1b9ca91c6edd3fb4fdeecb5"
            ),
            ModelFile(
                "decoder_kv.ort", "5c9a2bf2d9fc543fd4596b3ab4ab8d09f791aac5682eb1379fd8d59e34237db0"
            ),
            ModelFile(
                "encoder.ort", "6785ca9932d59265375249a8f3bc62f8333fb4dee6ab7db8dfd6f1daef66f59e"
            ),
            ModelFile(
                "frontend.model.ort",
                "04c552e66efe3f7206d0a69779864f93bf3cfaf2fa595c9ce5101c8e3854a414",
            ),
            ModelFile(
                "frontend.weights.ort",
                "6cc4d70efffe757452996574d11065e7dac6a7ff0a9be3e2fec1d0266b062b0e",
            ),
            ModelFile(
                "streaming_config.json",
                "d31afd7c2dd5ee9ae3fa232312c5b42cb3e4fe1c6e9c53d885f2bea63023790a",
            ),
            ModelFile(
                "tokenizer.bin", "3acea39a89cdf44fa11f10bfdd7d05d9015d901999f8c8fa18988f19dcc6b267"
            ),
        ),
    ),
}
