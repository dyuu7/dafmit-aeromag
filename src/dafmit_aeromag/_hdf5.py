from collections.abc import Iterable
from typing import cast

import h5py
import numpy as np

from .exceptions import DataIntegrityError

IDENTITY_COLUMNS = ("flight", "line", "year", "doy", "tt", "time")
SCALAR_FIELDS = frozenset({"N", "dt", "info"})


def integer_values(values: np.ndarray, name: str) -> np.ndarray:
    try:
        kind = np.asarray(values).dtype.kind
        if kind in "iu":
            if kind == "u" and np.any(values > np.iinfo(np.int64).max):
                raise ValueError("not representable as int64")
            return values.astype(np.int64)
        if kind != "f":
            raise ValueError("not a real numeric field")
        numeric = np.asarray(values, dtype=float)
        if (
            not np.all(np.isfinite(numeric))
            or not np.all(numeric == np.floor(numeric))
            or np.any(numeric < -(2**63))
            or np.any(numeric >= 2**63)
        ):
            raise ValueError("not representable as int64")
        return numeric.astype(np.int64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DataIntegrityError(
            f"identity field {name!r} contains invalid integers"
        ) from exc


def sample_count(handle: h5py.File) -> int:
    """Validate mandatory coordinates and scalar metadata; return the row count."""
    line, tt = handle.get("line"), handle.get("tt")
    if (
        not isinstance(line, h5py.Dataset)
        or not isinstance(tt, h5py.Dataset)
        or line.ndim != 1
        or tt.ndim != 1
        or line.shape != tt.shape
    ):
        raise DataIntegrityError(
            "HDF5 line/tt coordinates must share a one-dimensional sample shape"
        )
    count = int(tt.shape[0])
    for name in SCALAR_FIELDS:
        if name in handle:
            node = handle[name]
            if not isinstance(node, h5py.Dataset) or node.ndim != 0:
                raise DataIntegrityError(f"HDF5 {name!r} metadata must be scalar")
    if "N" in handle:
        declared = integer_values(np.asarray(cast(h5py.Dataset, handle["N"])[()]), "N")
        if int(declared) != count:
            raise DataIntegrityError(
                f"HDF5 N metadata does not match sample count ({count})"
            )
    sample_interval(handle)
    return count


def sample_interval(handle: h5py.File) -> float | None:
    if "dt" not in handle:
        return None
    try:
        node = handle["dt"]
        if (
            not isinstance(node, h5py.Dataset)
            or node.ndim != 0
            or node.dtype.kind not in "iuf"
        ):
            raise ValueError("not a numeric scalar")
        value = float(node[()])
        if not np.isfinite(value) or value <= 0:
            raise ValueError("not positive and finite")
        return value
    except (TypeError, ValueError, OverflowError) as exc:
        raise DataIntegrityError("HDF5 dt must be a positive finite scalar") from exc


def sample_fields(
    handle: h5py.File, count: int, documented: Iterable[str]
) -> dict[str, h5py.Dataset]:
    """List actual sample fields and reject malformed documented sample fields."""
    expected = set(documented) | {"line", "tt", "flight", "year", "doy"}
    fields = {}
    for name, node in handle.items():
        if name in SCALAR_FIELDS:
            continue
        if isinstance(node, h5py.Dataset) and node.shape == (count,):
            fields[name] = node
        elif name in expected:
            raise DataIntegrityError(
                f"field {name!r} must have sample shape ({count},)"
            )
    return fields
