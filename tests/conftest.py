from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pytest

from dafmit_aeromag import Dataset


@pytest.fixture
def synthetic_dataset(tmp_path: Path) -> Dataset:
    """Create small files that exercise both published collection shapes."""

    file_2020 = tmp_path / "Flt1002_train.h5"
    with h5py.File(file_2020, "w") as handle:
        handle.create_dataset("N", data=5)
        handle.create_dataset("dt", data=0.1)
        handle.create_dataset("info", data="synthetic 2020")
        handle.create_dataset(
            "line", data=np.array([1002.01, 1002.01, 1002.02, 1002.02, 320.0])
        )
        handle.create_dataset(
            "tt", data=np.array([45100.0, 45100.1, 45101.0, 45101.1, 56064.4])
        )
        handle.create_dataset("mag_1_uc", data=np.array([1.0, 2.0, 3.0, 4.0, 5.0]))
        handle.create_dataset("ins_lat", data=np.array([45.0, 45.1, 45.2, 45.3, 45.4]))

    file_2021 = tmp_path / "Flt2005_train.h5"
    with h5py.File(file_2021, "w") as handle:
        handle.create_dataset("N", data=3)
        handle.create_dataset("dt", data=0.1)
        handle.create_dataset("info", data="synthetic 2021")
        handle.create_dataset("line", data=np.array([2004.0, 2004.0, 2005.2]))
        handle.create_dataset("flight", data=np.array([2005.0, 2005.0, 2005.0]))
        handle.create_dataset("year", data=np.array([2021.0, 2021.0, 2021.0]))
        handle.create_dataset("doy", data=np.array([355.0, 355.0, 355.0]))
        handle.create_dataset("tt", data=np.array([54616.0, 54616.1, 54700.0]))
        handle.create_dataset("mag_1_uc", data=np.array([10.0, 11.0, 12.0]))
        handle.create_dataset("flux_a_x", data=np.array([20.0, 21.0, 22.0]))

    dataset = Dataset(data_dir=tmp_path, offline=True, progress=False)
    paths = {1002: file_2020, 2005: file_2021}
    dataset._get_path = lambda flight: paths[flight]  # type: ignore[method-assign]
    return dataset
