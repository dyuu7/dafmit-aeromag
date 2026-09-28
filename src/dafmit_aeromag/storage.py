"""Download files and reuse successful verification while their state is unchanged."""

from __future__ import annotations

import hashlib
from pathlib import Path

import h5py
import pooch

from ._hdf5 import sample_count
from .catalog_core import FileSpec
from .exceptions import DataIntegrityError, DataUnavailableError


def file_state(path: Path) -> tuple[int, int, int, int, int]:
    try:
        stat = path.stat()
        return (
            stat.st_dev,
            stat.st_ino,
            stat.st_size,
            stat.st_mtime_ns,
            stat.st_ctime_ns,
        )
    except OSError as exc:
        raise DataUnavailableError(f"could not inspect local file {path}") from exc


def _digest(path: Path) -> str:
    hasher = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_file(path: Path, spec: FileSpec) -> None:
    """Check exact bytes and coordinate structure without caching the result."""
    if not path.is_file():
        raise DataIntegrityError(f"expected data file does not exist: {path}")
    before = file_state(path)
    if before[2] != spec.size_bytes:
        raise DataIntegrityError(
            f"size mismatch for {path.name}: expected {spec.size_bytes}, "
            f"found {before[2]} bytes"
        )
    try:
        if _digest(path).lower() != spec.checksum.lower():
            raise DataIntegrityError(f"checksum mismatch for {path.name}")
        with h5py.File(path, "r") as handle:
            sample_count(handle)
    except OSError as exc:
        raise DataIntegrityError(f"could not inspect HDF5 file {path}: {exc}") from exc
    if file_state(path) != before:
        raise DataIntegrityError(f"file changed during verification: {path}")


class FileStore:
    """Instance-local verification records; no retained HDF5 handles."""

    def __init__(self, data_dir: Path, *, progress: bool, offline: bool) -> None:
        self.data_dir = data_dir
        self.progress = progress
        self.offline = offline
        self._verified: dict[Path, tuple[FileSpec, tuple[int, int, int, int, int]]] = {}

    def check_unchanged(self, paths: list[Path]) -> None:
        """Reject results if a verified file changed while it was being read."""
        for path in paths:
            record = self._verified.get(path)
            if record is None or file_state(path) != record[1]:
                self._verified.pop(path, None)
                raise DataIntegrityError(f"file changed during read: {path}")

    def fetch(self, spec: FileSpec, *, recheck: bool = False) -> Path:
        path = self.data_dir / spec.file
        if not path.exists():
            self._verified.pop(path, None)
            if self.offline:
                raise DataUnavailableError(
                    f"{path.name} is not present in offline mode; "
                    "place the Zenodo file "
                    f"in {self.data_dir} or disable offline mode"
                )
            try:
                self.data_dir.mkdir(parents=True, exist_ok=True)
                # Pooch verifies a temporary download before moving it into place.
                pooch.retrieve(
                    url=spec.url,
                    known_hash=f"md5:{spec.checksum}",
                    fname=spec.file,
                    path=self.data_dir,
                    progressbar=self.progress,
                )
            except ValueError as exc:
                raise DataIntegrityError(
                    f"download failed verification for {spec.file}: {exc}"
                ) from exc
            except Exception as exc:
                raise DataUnavailableError(
                    f"could not download {spec.file}: {exc}"
                ) from exc
        state = file_state(path)
        if recheck or self._verified.get(path) != (spec, state):
            self._verified.pop(path, None)
            verify_file(path, spec)
            if file_state(path) != state:
                raise DataIntegrityError(f"file changed during verification: {path}")
            self._verified[path] = (spec, state)
        return path
