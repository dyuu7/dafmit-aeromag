from __future__ import annotations

import hashlib
from pathlib import Path

import h5py
import pytest

from dafmit_aeromag.catalog_core import FileSpec
from dafmit_aeromag.exceptions import DataIntegrityError
from dafmit_aeromag.storage import verify_file


def test_verify_file_checks_size_checksum_and_hdf5(tmp_path: Path) -> None:
    path = tmp_path / "sample.h5"
    with h5py.File(path, "w") as handle:
        handle.create_dataset("line", data=[1.0])
        handle.create_dataset("tt", data=[2.0])
    digest = hashlib.md5(path.read_bytes()).hexdigest()
    spec = FileSpec(
        1,
        "2020",
        "2020-01-01",
        path.name,
        "https://example.invalid",
        path.stat().st_size,
        digest,
        0.1,
        False,
    )

    verify_file(path, spec)
    path.write_bytes(path.read_bytes() + b"x")
    with pytest.raises(DataIntegrityError, match="size mismatch"):
        verify_file(path, spec)


def test_verify_file_checks_declared_sample_count(tmp_path: Path) -> None:
    path = tmp_path / "bad-count.h5"
    with h5py.File(path, "w") as handle:
        handle.create_dataset("N", data=2)
        handle.create_dataset("line", data=[1.0])
        handle.create_dataset("tt", data=[2.0])
    spec = FileSpec(
        1,
        "2020",
        "2020-01-01",
        path.name,
        "https://example.invalid",
        path.stat().st_size,
        hashlib.md5(path.read_bytes()).hexdigest(),
        0.1,
        False,
    )

    with pytest.raises(DataIntegrityError, match="sample count"):
        verify_file(path, spec)


def test_verify_file_checks_line_and_tt_shapes(tmp_path: Path) -> None:
    path = tmp_path / "bad-shape.h5"
    with h5py.File(path, "w") as handle:
        handle.create_dataset("line", data=[1.0, 2.0])
        handle.create_dataset("tt", data=[2.0])
    spec = FileSpec(
        1,
        "2020",
        "2020-01-01",
        path.name,
        "https://example.invalid",
        path.stat().st_size,
        hashlib.md5(path.read_bytes()).hexdigest(),
        0.1,
        False,
    )

    with pytest.raises(DataIntegrityError, match="line/tt"):
        verify_file(path, spec)
