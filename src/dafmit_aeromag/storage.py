"""Local storage and integrity checks for release files."""

from __future__ import annotations

import hashlib
from pathlib import Path

import h5py
import pooch

from .catalog_core import FileSpec
from .exceptions import DataIntegrityError, DataUnavailableError


def _digest(path: Path, algorithm: str) -> str:
    hasher = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_file(path: Path, spec: FileSpec) -> None:
    """Validate a downloaded file against the catalog's size and MD5."""

    if not path.is_file():
        raise DataIntegrityError(f"expected data file does not exist: {path}")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise DataIntegrityError(f"could not stat data file: {path}") from exc
    if size != spec.size_bytes:
        raise DataIntegrityError(
            f"size mismatch for {path.name}: expected {spec.size_bytes} bytes, "
            f"found {size}"
        )
    algorithm, expected = "md5", spec.checksum
    try:
        actual = _digest(path, algorithm)
    except OSError as exc:
        raise DataIntegrityError(f"could not read data file: {path}") from exc
    if actual.lower() != expected.lower():
        raise DataIntegrityError(
            f"checksum mismatch for {path.name}: expected {expected}, found {actual}"
        )
    try:
        is_hdf5 = h5py.is_hdf5(path)
    except OSError as exc:
        raise DataIntegrityError(f"could not identify HDF5 data file: {path}") from exc
    if not is_hdf5:
        raise DataIntegrityError(f"file is not a readable HDF5 file: {path}")
    try:
        with h5py.File(path, "r") as handle:
            sample = handle.get("tt")
            line = handle.get("line")
            declared = handle.get("N")
            if (
                sample is None
                or line is None
                or not isinstance(sample, h5py.Dataset)
                or not isinstance(line, h5py.Dataset)
            ):
                raise DataIntegrityError(
                    f"HDF5 file has no one-dimensional line/tt coordinates: {path}"
                )
            if sample.ndim != 1 or line.ndim != 1 or sample.shape != line.shape:
                raise DataIntegrityError(
                    "HDF5 line/tt coordinates do not share a one-dimensional "
                    f"shape: {path}"
                )
            if declared is not None and isinstance(declared, h5py.Dataset):
                if declared.ndim != 0:
                    raise DataIntegrityError(f"HDF5 N metadata is not scalar: {path}")
                if int(declared[()]) != sample.shape[0]:
                    raise DataIntegrityError(
                        f"HDF5 N metadata does not match sample count in {path.name}"
                    )
    except DataIntegrityError:
        raise
    except (OSError, TypeError, ValueError, OverflowError) as exc:
        raise DataIntegrityError(f"could not inspect HDF5 structure: {path}") from exc


def resolve_file(
    spec: FileSpec,
    *,
    data_dir: Path,
    progress: bool,
    offline: bool,
) -> Path:
    """Return a verified local file, downloading it when necessary."""

    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DataUnavailableError(
            f"could not create data directory {data_dir}"
        ) from exc
    path = data_dir / spec.file
    if path.exists():
        verify_file(path, spec)
        return path
    if offline:
        raise DataUnavailableError(
            f"{path.name} is not present in offline mode; place the Zenodo file in "
            f"{data_dir} or disable offline mode"
        )
    try:
        downloaded = Path(
            pooch.retrieve(
                url=spec.url,
                known_hash=f"md5:{spec.checksum}",
                fname=spec.file,
                path=data_dir,
                progressbar=progress,
            )
        )
    except Exception as exc:
        raise DataUnavailableError(
            f"could not download {spec.file} from {spec.url}: {exc}"
        ) from exc
    verify_file(downloaded, spec)
    return downloaded
