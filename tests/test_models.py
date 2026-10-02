import hashlib
from collections.abc import Iterable
from pathlib import Path

import pytest

from voxar.domain import (
    ConfigError,
    LicenseNotAcceptedError,
    ModelIntegrityError,
    ModelNotFoundError,
    OfflineModeError,
)
from voxar.models import ModelFile, ModelSpec, ModelStore

PAYLOAD = b"fake model bytes"
GOOD_SHA = hashlib.sha256(PAYLOAD).hexdigest()


def spec(sha: str = GOOD_SHA, name: str = "weights.bin") -> ModelSpec:
    return ModelSpec(
        id="demo",
        revision="r1",
        license="MIT",
        source="https://example.invalid/demo",
        files=(ModelFile(name=name, sha256=sha),),
    )


def fetch_ok(_: ModelFile) -> Iterable[bytes]:
    yield PAYLOAD[:5]
    yield PAYLOAD[5:]


def test_spec_rejects_path_traversal_names() -> None:
    for bad in ("../x", "a/b", "..", ""):
        with pytest.raises(ConfigError, match="file name"):
            spec(name=bad)


def test_spec_rejects_malformed_sha() -> None:
    with pytest.raises(ConfigError, match="sha256"):
        spec(sha="not-a-hash")


def test_install_verifies_and_stores(tmp_path: Path) -> None:
    store = ModelStore(tmp_path)
    target = store.install(spec(), fetch_ok, accept_license=True)
    assert (target / "weights.bin").read_bytes() == PAYLOAD
    assert store.is_installed(spec())
    store.verify(spec())  # does not raise


def test_install_requires_license_acceptance(tmp_path: Path) -> None:
    with pytest.raises(LicenseNotAcceptedError, match="MIT"):
        ModelStore(tmp_path).install(spec(), fetch_ok, accept_license=False)
    assert not (tmp_path / "demo").exists()


def test_install_refused_in_offline_mode(tmp_path: Path) -> None:
    with pytest.raises(OfflineModeError):
        ModelStore(tmp_path, offline=True).install(spec(), fetch_ok, accept_license=True)


def test_hash_mismatch_is_rejected_and_leaves_nothing_behind(tmp_path: Path) -> None:
    bad = spec(sha="0" * 64)
    store = ModelStore(tmp_path)
    with pytest.raises(ModelIntegrityError, match="weights.bin"):
        store.install(bad, fetch_ok, accept_license=True)
    assert not store.is_installed(bad)
    leftovers = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert leftovers == []


def test_verify_missing_model(tmp_path: Path) -> None:
    with pytest.raises(ModelNotFoundError, match="voxar models"):
        ModelStore(tmp_path).verify(spec())


def test_verify_detects_tampering(tmp_path: Path) -> None:
    store = ModelStore(tmp_path)
    target = store.install(spec(), fetch_ok, accept_license=True)
    (target / "weights.bin").write_bytes(b"tampered")
    with pytest.raises(ModelIntegrityError):
        store.verify(spec())
