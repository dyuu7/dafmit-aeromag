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
    )

    with pytest.raises(DataIntegrityError, match="line/tt"):
        verify_file(path, spec)


def test_verification_is_reused_per_instance_and_recheck_forces_it(
    synthetic_dataset, monkeypatch
):
    from dafmit_aeromag import Dataset, Selection, storage

    original = storage._digest
    calls = []

    def counted(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(storage, "_digest", counted)
    data = synthetic_dataset
    for _ in range(3):
        data.read(Selection(1002, tt=slice(45100, 45100.05)), columns="mag_1_uc")
    assert len(calls) == 1
    data.inspect(1002)
    assert len(calls) == 1
    data.fetch(1002, recheck=True)
    assert len(calls) == 2
    Dataset(data_dir=data.data_dir, offline=True).fetch(1002)
    assert len(calls) == 3


def test_same_size_change_invalidates_verification(synthetic_dataset):
    from dafmit_aeromag import Selection

    data = synthetic_dataset
    path = data.fetch(1002)[1002]
    size = path.stat().st_size
    with h5py.File(path, "r+") as handle:
        handle["mag_1_uc"][0] = 900.0
    assert path.stat().st_size == size
    with pytest.raises(DataIntegrityError, match="checksum"):
        data.read(Selection(1002), columns="mag_1_uc")
    # A failed verification must never become a trusted cache entry.
    with pytest.raises(DataIntegrityError, match="checksum"):
        data.fetch(1002)


def test_file_change_during_read_rejects_result(synthetic_dataset, monkeypatch):
    import dafmit_aeromag.dataset as interface
    from dafmit_aeromag import Selection

    original = interface.read_files
    path = synthetic_dataset.fetch(1002)[1002]

    def modified_after_read(*args, **kwargs):
        result = original(*args, **kwargs)
        with h5py.File(path, "r+") as handle:
            handle["mag_1_uc"][0] = 900.0
        return result

    monkeypatch.setattr(interface, "read_files", modified_after_read)
    with pytest.raises(DataIntegrityError, match="changed during read"):
        synthetic_dataset.read(Selection(1002), columns="mag_1_uc")


@pytest.mark.parametrize("raw", [False, True])
def test_batch_reads_each_native_coordinate_once(synthetic_dataset, monkeypatch, raw):
    from collections import Counter

    from dafmit_aeromag import Selection

    data = synthetic_dataset
    data.fetch(2005)
    original = h5py.Dataset.__getitem__
    reads = Counter()
    coordinates = {"/line", "/tt", "/flight", "/year", "/doy"}

    def counted(self, key, *args, **kwargs):
        if self.name in coordinates and isinstance(key, slice):
            reads[self.name] += 1
        return original(self, key, *args, **kwargs)

    monkeypatch.setattr(h5py.Dataset, "__getitem__", counted)
    data.read(
        [Selection(2005), Selection(2005, lines="2004.00")],
        columns="all",
        raw=raw,
    )
    assert reads == dict.fromkeys(coordinates, 1)


@pytest.mark.parametrize("failure", [False, True])
def test_batch_opens_each_file_once_and_releases_handles(
    synthetic_dataset, monkeypatch, failure
):
    from dafmit_aeromag import NoDataError, Selection

    data = synthetic_dataset
    data.fetch([1002, 2005])
    original = h5py.File
    handles = []

    def tracked(*args, **kwargs):
        handle = original(*args, **kwargs)
        handles.append(handle)
        return handle

    monkeypatch.setattr(h5py, "File", tracked)
    query = [
        Selection(1002),
        Selection(2005, lines="9999") if failure else Selection(2005),
        Selection(1002),
    ]
    if failure:
        with pytest.raises(NoDataError):
            data.read(query, columns="mag_1_uc")
    else:
        data.read(query, columns="mag_1_uc")
    assert len(handles) == 2
    assert all(not handle.id.valid for handle in handles)


def test_download_is_verified_before_use(synthetic_dataset, tmp_path, monkeypatch):
    from dafmit_aeromag import Dataset, storage

    source = synthetic_dataset.fetch(1002)[1002]
    calls = []

    def download(**kwargs):
        target = Path(kwargs["path"]) / kwargs["fname"]
        target.write_bytes(source.read_bytes())
        calls.append(kwargs)
        return str(target)

    monkeypatch.setattr(storage.pooch, "retrieve", download)
    target = Dataset(data_dir=tmp_path / "downloads", progress=False)
    assert target.inspect(1002).sample_count == 5
    assert (
        calls[0]["known_hash"] == "md5:" + hashlib.md5(source.read_bytes()).hexdigest()
    )
    target.fetch(1002)
    assert len(calls) == 1


def test_failed_download_and_corrupt_download_are_distinct(
    synthetic_dataset, tmp_path, monkeypatch
):
    from dafmit_aeromag import Dataset, DataUnavailableError, storage

    def unavailable(**kwargs):
        raise OSError("network down")

    monkeypatch.setattr(storage.pooch, "retrieve", unavailable)
    data = Dataset(data_dir=tmp_path / "download")
    with pytest.raises(DataUnavailableError, match="network down"):
        data.fetch(1002)

    def bad_checksum(**kwargs):
        raise ValueError("MD5 hash does not match the known hash")

    monkeypatch.setattr(storage.pooch, "retrieve", bad_checksum)
    with pytest.raises(DataIntegrityError, match="MD5 hash"):
        data.fetch(1002)

    def corrupt(**kwargs):
        target = Path(kwargs["path"]) / kwargs["fname"]
        target.write_bytes(b"not hdf5")
        return str(target)

    monkeypatch.setattr(storage.pooch, "retrieve", corrupt)
    with pytest.raises(DataIntegrityError):
        data.fetch(1002)
