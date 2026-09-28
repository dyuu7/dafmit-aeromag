"""Public behavior checked against checksum-pinned files from both collections."""

from __future__ import annotations

import os

import h5py
import numpy as np
import pytest

from dafmit_aeromag import Dataset, NoDataError, Selection, to_xarray

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("MAGNAV_INTEGRATION") != "1",
        reason="set MAGNAV_INTEGRATION=1 to inspect real Zenodo files",
    ),
]


@pytest.fixture(scope="module")
def real_data(tmp_path_factory):
    existing = os.environ.get("MAGNAV_DATA_DIR")
    return Dataset(
        data_dir=existing or tmp_path_factory.mktemp("zenodo"),
        offline=bool(existing),
        progress=False,
    )


@pytest.mark.parametrize(("flight", "expected"), [(1004, 81408), (2005, 6361)])
def test_complete_file_matches_source(real_data, flight, expected):
    info = real_data.inspect(flight)
    frame = real_data.read(Selection.all(flight), columns="mag_1_uc")
    raw = real_data.read(
        Selection.all(flight), columns=["line", "tt", "mag_1_uc"], raw=True
    )
    assert info.sample_count == expected
    assert len(frame) == expected
    assert len(raw) == expected
    with h5py.File(info.path, "r") as source:
        assert source["N"][()] == expected
        for name in ["tt", "mag_1_uc"]:
            np.testing.assert_array_equal(frame[name], source[name][:])
            np.testing.assert_array_equal(raw[name], source[name][:])
        np.testing.assert_array_equal(raw.line, source["line"][:])
    assert to_xarray(frame).time.dtype == np.dtype("datetime64[ns]")


def test_2005_boundary_belongs_to_transit(real_data):
    frame = real_data.read(Selection(2005, lines="2004.00"), columns="mag_1_uc")
    assert len(frame) == 6361
    assert frame.tt.iloc[-1] == 55252.0
    assert frame.line.iloc[-1] == "2004.00"
    assert (
        len(real_data.read(Selection(2005, tt=slice(54616, 55252)), columns="mag_1_uc"))
        == 6360
    )
    after_boundary = real_data.read(
        Selection(2005, tt=slice(55252, None)), columns="mag_1_uc"
    )
    assert len(after_boundary) == 1
    assert after_boundary.line.iloc[0] == "2004.00"


@pytest.mark.parametrize(
    ("flight", "line"), [(1004, "4014.00"), (1004, "4013.00"), (2005, "2004.01")]
)
def test_documented_holdout_lines_have_no_samples(real_data, flight, line):
    query = Selection(flight, lines=line)
    with pytest.raises(NoDataError):
        real_data.read(query, columns="mag_1_uc")
    assert real_data.read(query, columns="mag_1_uc", empty="allow").empty


def test_2020_gap_and_field_discovery(real_data):
    info = real_data.inspect(1004)
    missing = set(real_data.fields(flight=1004).name) - set(info.fields.name)
    assert missing == {"mag_6_uc", "year", "doy"}
    frame = real_data.read(Selection.all(1004), columns=info.fields.name)
    index = np.flatnonzero(frame.tt.to_numpy() == 52862.1)[0]
    assert frame.tt.iloc[index + 1] == 54518.2
    assert frame.year.eq(2020).all()
    assert frame.doy.eq(182).all()
