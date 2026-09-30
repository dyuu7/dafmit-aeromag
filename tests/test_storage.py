from __future__ import annotations

import errno
import hashlib
import os
import stat
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from multiprocessing import get_context
from pathlib import Path

import h5py
import pytest
from filelock import FileLock

from dafmit_aeromag.catalog_core import FileSpec
from dafmit_aeromag.exceptions import DataIntegrityError, DataUnavailableError
from dafmit_aeromag.storage import FileStore, verify_file


def _fetch_in_process(spec, directory, barrier, results):
    try:
        if os.name == "posix":
            os.umask(0o007)
        barrier.wait(timeout=20)
        path = FileStore(Path(directory), progress=False, offline=False).fetch(spec)
        results.put(("ok", hashlib.md5(path.read_bytes()).hexdigest()))
    except Exception as exc:
        results.put(("error", repr(exc)))


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
    directory = tmp_path / "downloads"

    def download(self, url, output_file, pooch):
        Path(output_file).write_bytes(source.read_bytes())
        assert not (directory / source.name).exists()
        assert self.progressbar is False
        calls.append(url)

    monkeypatch.setattr(storage.pooch.HTTPDownloader, "__call__", download)
    target = Dataset(data_dir=directory, progress=False)
    assert target.inspect(1002).sample_count == 5
    target.fetch(1002)
    assert len(calls) == 1


@pytest.mark.parametrize("offline", [False, True])
def test_existing_files_work_in_read_only_directory(
    synthetic_dataset, monkeypatch, offline
):
    from dafmit_aeromag import Dataset, storage

    def unexpected_lock(*args, **kwargs):
        pytest.fail("reading an existing file must not create a lock")

    monkeypatch.setattr(storage, "FileLock", unexpected_lock)
    directory = synthetic_dataset.data_dir
    original_mode = stat.S_IMODE(directory.stat().st_mode)
    original_files = set(directory.iterdir())
    try:
        directory.chmod(0o555)
        data = Dataset(data_dir=directory, offline=offline)
        assert data.inspect(1002).sample_count == 5
        assert set(directory.iterdir()) == original_files
    finally:
        directory.chmod(original_mode)


def test_shared_first_download_is_single_across_processes(synthetic_dataset, tmp_path):
    source = synthetic_dataset.fetch(1002)[1002]
    payload = source.read_bytes()
    checksum = hashlib.md5(payload).hexdigest()
    requests = []

    class DownloadHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            time.sleep(0.3)
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), DownloadHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    context = get_context("spawn")
    barrier = context.Barrier(2)
    results = context.Queue()
    shared = tmp_path / "shared"
    spec = FileSpec(
        1002,
        "2020",
        "2020-06-20",
        source.name,
        f"http://127.0.0.1:{server.server_port}/{source.name}",
        len(payload),
        checksum,
        0.1,
    )
    processes = [
        context.Process(target=_fetch_in_process, args=(spec, shared, barrier, results))
        for _ in range(2)
    ]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=30)
        assert [process.exitcode for process in processes] == [0, 0]
        assert [results.get(timeout=5) for _ in processes] == [
            ("ok", checksum),
            ("ok", checksum),
        ]
        assert requests == [f"/{source.name}"]
        lock_path = shared / f".{source.name}.lock"
        assert lock_path.is_file()
        if os.name == "posix":
            assert stat.S_IMODE((shared / source.name).stat().st_mode) == 0o660
            assert stat.S_IMODE(lock_path.stat().st_mode) == 0o660
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)


def test_missing_file_lock_timeout_is_explicit(
    synthetic_dataset, tmp_path, monkeypatch
):
    from dafmit_aeromag import Dataset, storage

    target = tmp_path / "shared"
    target.mkdir()
    lock_path = target / ".Flt1002_train.h5.lock"
    monkeypatch.setattr(storage, "_DOWNLOAD_LOCK_TIMEOUT", 0.1)
    with FileLock(lock_path):
        data = Dataset(data_dir=target, progress=False)
        with pytest.raises(DataUnavailableError, match="timed out waiting"):
            data.fetch(1002)
    assert not (target / "Flt1002_train.h5").exists()


def test_unavailable_download_lock_is_explicit(
    synthetic_dataset, tmp_path, monkeypatch
):
    from dafmit_aeromag import Dataset, storage

    fcntl = pytest.importorskip("fcntl")

    def unavailable_lock(*args, **kwargs):
        raise OSError(errno.ENOSYS, "filesystem locks unavailable")

    def unexpected_download(*args, **kwargs):
        pytest.fail("an unsupported file lock must prevent downloading")

    monkeypatch.setattr(fcntl, "flock", unavailable_lock)
    monkeypatch.setattr(storage.pooch.HTTPDownloader, "__call__", unexpected_download)
    data = Dataset(data_dir=tmp_path / "shared", progress=False)
    with pytest.raises(DataUnavailableError, match="filesystem locks unavailable"):
        data.fetch(1002)


def test_failed_download_and_corrupt_download_are_distinct(
    synthetic_dataset, tmp_path, monkeypatch
):
    from dafmit_aeromag import Dataset, DataUnavailableError, storage

    source = synthetic_dataset.fetch(1002)[1002]
    directory = tmp_path / "download"

    def unavailable(self, url, output_file, pooch):
        Path(output_file).write_bytes(b"partial download")
        raise OSError("network down")

    monkeypatch.setattr(storage.pooch.HTTPDownloader, "__call__", unavailable)
    data = Dataset(data_dir=directory)
    with pytest.raises(DataUnavailableError, match="network down"):
        data.fetch(1002)
    assert [path.name for path in directory.iterdir()] == [f".{source.name}.lock"]

    def bad_checksum(self, url, output_file, pooch):
        payload = source.read_bytes()
        Path(output_file).write_bytes(bytes([payload[0] ^ 1]) + payload[1:])

    monkeypatch.setattr(storage.pooch.HTTPDownloader, "__call__", bad_checksum)
    with pytest.raises(DataIntegrityError, match="checksum mismatch"):
        data.fetch(1002)
    assert [path.name for path in directory.iterdir()] == [f".{source.name}.lock"]

    def corrupt(self, url, output_file, pooch):
        Path(output_file).write_bytes(b"not hdf5")

    monkeypatch.setattr(storage.pooch.HTTPDownloader, "__call__", corrupt)
    with pytest.raises(DataIntegrityError, match="size mismatch"):
        data.fetch(1002)
    assert [path.name for path in directory.iterdir()] == [f".{source.name}.lock"]

    def complete(self, url, output_file, pooch):
        Path(output_file).write_bytes(source.read_bytes())

    monkeypatch.setattr(storage.pooch.HTTPDownloader, "__call__", complete)
    assert data.fetch(1002)[1002].read_bytes() == source.read_bytes()
