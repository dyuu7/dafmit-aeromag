from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

import h5py
import pooch
from filelock import FileLock, Timeout

from ._hdf5 import sample_count
from .catalog_core import FileSpec
from .exceptions import DataIntegrityError, DataUnavailableError

_DOWNLOAD_LOCK_TIMEOUT = 3600


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

    def _verified_path(self, path: Path, spec: FileSpec, *, recheck: bool) -> Path:
        state = file_state(path)
        if recheck or self._verified.get(path) != (spec, state):
            self._verified.pop(path, None)
            verify_file(path, spec)
            if file_state(path) != state:
                raise DataIntegrityError(f"file changed during verification: {path}")
            self._verified[path] = (spec, state)
        return path

    def _download(self, path: Path, spec: FileSpec) -> None:
        try:
            with TemporaryDirectory(
                prefix=f".{path.name}.", dir=self.data_dir
            ) as directory:
                temporary = Path(directory) / path.name
                # Normal file creation preserves umask and inherited directory ACLs.
                downloader = pooch.HTTPDownloader(progressbar=self.progress)
                downloader(spec.url, temporary, None)
                verify_file(temporary, spec)
                temporary.replace(path)
        except DataIntegrityError:
            raise
        except Exception as exc:
            raise DataUnavailableError(
                f"could not download {spec.file}: {exc}"
            ) from exc

    def fetch(self, spec: FileSpec, *, recheck: bool = False) -> Path:
        path = self.data_dir / spec.file
        if path.exists():
            return self._verified_path(path, spec, recheck=recheck)
        self._verified.pop(path, None)
        if self.offline:
            raise DataUnavailableError(
                f"{path.name} is not present in offline mode; "
                "place the Zenodo file "
                f"in {self.data_dir} or disable offline mode"
            )
        lock_path = path.with_name(f".{path.name}.lock")
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with FileLock(
                lock_path,
                timeout=_DOWNLOAD_LOCK_TIMEOUT,
                fallback_to_soft=False,
                preserve_lock_file=True,
            ):
                if not path.exists():
                    self._download(path, spec)
                return self._verified_path(path, spec, recheck=recheck)
        except Timeout as exc:
            raise DataUnavailableError(
                f"timed out waiting for download lock for {path}"
            ) from exc
        except OSError as exc:
            raise DataUnavailableError(
                f"could not access download directory or lock for {path}: {exc}"
            ) from exc
