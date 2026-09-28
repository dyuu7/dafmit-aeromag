from __future__ import annotations

import builtins

import numpy as np
import pandas as pd
import pytest

from dafmit_aeromag import InvalidArgumentError, Selection, to_xarray


def test_xarray_has_real_utc_datetimes_and_units(synthetic_dataset):
    frame = synthetic_dataset.read(Selection(1002), columns="mag_1_uc")
    result = to_xarray(frame)
    assert result.sizes["sample"] == 5
    assert result.time.dtype == np.dtype("datetime64[ns]")
    assert result.time.attrs["timezone"] == "UTC"
    assert result.time.dt.hour.values[0] == 12
    assert result.mag_1_uc.attrs["units"] == "nT"
    expected = frame.time.dt.tz_localize(None).to_numpy(dtype="datetime64[ns]")
    np.testing.assert_array_equal(result.time.values, expected)
    timed = result.swap_dims({"sample": "time"})
    assert (
        timed.sel(time=slice("2020-06-20T12:31:40", "2020-06-20T12:31:40.1")).sizes[
            "time"
        ]
        == 2
    )
    result.attrs["selections"][0]["row_count"] = 999
    assert frame.attrs["selections"][0]["row_count"] == 5


def test_empty_raw_and_repeated_times_convert(synthetic_dataset):
    data = synthetic_dataset
    frame = data.read([Selection(1002), Selection(1002)], columns="mag_1_uc")
    result = to_xarray(frame)
    assert result.sizes["sample"] == 10
    assert len(np.unique(result.time)) == 5
    empty = to_xarray(
        data.read(Selection(1002, lines="9999"), columns="mag_1_uc", empty="allow")
    )
    assert empty.sizes["sample"] == 0
    assert empty.time.dtype == np.dtype("datetime64[ns]")
    raw = to_xarray(data.read(Selection(1002), columns="mag_1_uc", raw=True))
    assert "time" not in raw
    assert raw.sizes["sample"] == 5


def test_conversion_respects_timezone_offsets():
    frame = pd.DataFrame({"time": pd.to_datetime(["2021-12-21T23:10:16+08:00"])})
    result = to_xarray(frame)
    assert result.time.values[0] == np.datetime64("2021-12-21T15:10:16")


def test_optional_dependency_has_actionable_error(monkeypatch):
    original = builtins.__import__

    def without_xarray(name, *args, **kwargs):
        if name == "xarray":
            raise ImportError("not installed")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_xarray)
    with pytest.raises(ImportError, match=r"dafmit-aeromag\[xarray\]"):
        to_xarray(pd.DataFrame())


@pytest.mark.parametrize(
    "frame",
    [
        pd.DataFrame({"time": ["not-a-time"]}),
        pd.DataFrame([[1, 2]], columns=["mag", "mag"]),
        pd.DataFrame({"sample": [1]}),
    ],
)
def test_bad_conversion_input_is_clear(frame):
    with pytest.raises(InvalidArgumentError):
        to_xarray(frame)
