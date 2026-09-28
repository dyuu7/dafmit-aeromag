"""Optional conversions of already loaded data; no dataset state is required."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from ._hdf5 import IDENTITY_COLUMNS
from .exceptions import InvalidArgumentError

if TYPE_CHECKING:
    import xarray as xr


def to_xarray(frame: pd.DataFrame) -> xr.Dataset:
    """Convert a read result to xarray, retaining every sample and its order.

    The sample dimension remains distinct from time because timestamps can repeat
    across flights or overlapping selections. UTC times become datetime64[ns]
    coordinates, with ``timezone='UTC'`` metadata. For a single suitable time
    series, use ``swap_dims({'sample': 'time'})`` to explicitly index by time.
    """
    try:
        import xarray as xr
    except ImportError as exc:
        raise ImportError(
            "xarray support is optional; install 'dafmit-aeromag[xarray]'"
        ) from exc
    if not isinstance(frame, pd.DataFrame) or not frame.columns.is_unique:
        raise InvalidArgumentError("to_xarray requires a DataFrame with unique columns")
    if (
        any(not isinstance(name, str) for name in frame.columns)
        or "sample" in frame.columns
    ):
        raise InvalidArgumentError(
            "columns must be strings and must not use reserved dimension 'sample'"
        )
    coords: dict[str, Any] = {"sample": np.arange(len(frame), dtype=np.int64)}
    variables: dict[str, Any] = {}
    for name in frame.columns:
        series = frame[name]
        if name == "time":
            if not pd.api.types.is_datetime64_any_dtype(series.dtype):
                raise InvalidArgumentError("time must contain datetime values")
            if isinstance(series.dtype, pd.DatetimeTZDtype):
                series = series.dt.tz_convert("UTC").dt.tz_localize(None)
            values = series.to_numpy(dtype="datetime64[ns]")
        else:
            values = series.to_numpy()
        target = coords if name in IDENTITY_COLUMNS else variables
        target[name] = ("sample", values)
    result = xr.Dataset(data_vars=variables, coords=coords, attrs=deepcopy(frame.attrs))
    for name, unit in frame.attrs.get("units", {}).items():
        if name in result:
            result[name].attrs["units"] = unit
    if "time" in result:
        result.time.attrs["timezone"] = "UTC"
    return result
