from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path

import h5py
import numpy as np
import pytest

from dafmit_aeromag import Dataset, catalog_core


@pytest.fixture
def dataset_factory(tmp_path: Path, monkeypatch):
    """Use small actual files with matching test manifest checksums."""
    load_catalog = catalog_core._catalog_data
    base = deepcopy(load_catalog("v3"))
    counter = 0

    def create(mutate=None):
        nonlocal counter
        counter += 1
        directory = tmp_path / str(counter)
        directory.mkdir()
        files = {
            1002: {
                "N": 5,
                "dt": 0.1,
                "info": "synthetic 2020",
                "line": np.array([1002.01, 1002.01, 1002.02, 1002.02, 320.0]),
                "tt": np.array([45100.0, 45100.1, 45101.0, 45101.1, 56064.4]),
                "mag_1_uc": np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
                "ins_lat": np.array([45.0, 45.1, 45.2, 45.3, 45.4]),
            },
            2005: {
                "N": 3,
                "dt": 0.1,
                "info": "synthetic 2021",
                "line": np.array([2004.0, 2004.0, 2004.0]),
                "flight": np.array([2005.0, 2005.0, 2005.0]),
                "year": np.array([2021.0, 2021.0, 2021.0]),
                "doy": np.array([355.0, 355.0, 355.0]),
                "tt": np.array([54616.0, 54616.1, 55252.0]),
                "mag_1_uc": np.array([10.0, 11.0, 12.0]),
                "flux_a_x": np.array([20.0, 21.0, 22.0]),
            },
        }
        if mutate is not None:
            mutate(files)
        manifest = deepcopy(base)
        for flight, fields in files.items():
            path = directory / f"Flt{flight}_train.h5"
            with h5py.File(path, "w") as handle:
                for name, values in fields.items():
                    handle.create_dataset(name, data=values)
            spec = next(row for row in manifest["flights"] if row["flight"] == flight)
            spec["size_bytes"] = path.stat().st_size
            spec["checksum"] = hashlib.md5(path.read_bytes()).hexdigest()
        monkeypatch.setattr(
            catalog_core,
            "_catalog_data",
            lambda release: manifest if release == "v3" else load_catalog(release),
        )
        return Dataset(data_dir=directory, offline=True, progress=False)

    return create


@pytest.fixture
def synthetic_dataset(dataset_factory) -> Dataset:
    return dataset_factory()
