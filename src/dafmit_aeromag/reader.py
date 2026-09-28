"""Read actual HDF5 samples. Readme annotations never filter rows here."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any, Literal

import h5py
import numpy as np
import pandas as pd

from ._hdf5 import (
    IDENTITY_COLUMNS,
    integer_values,
    sample_count,
    sample_fields,
    sample_interval,
)
from .catalog_core import Catalog, FileSpec
from .exceptions import (
    DataIntegrityError,
    InvalidArgumentError,
    MissingFieldError,
    NoDataError,
    UnknownFieldError,
)
from .selection import Selection


@dataclass(frozen=True)
class FlightInfo:
    """A detached report describing a verified flight file.

    ``fields`` lists actual one-dimensional sample fields, including undocumented
    ones. Its columns are name, dtype, units, description, group, and source_url.
    This table is independent of internal state and may be edited by the caller.
    ``dt`` is the declared interval, not a guarantee that samples are continuous.
    ``tt_range`` contains the minimum and maximum native times, or None if empty.
    """

    flight: int
    path: Path
    sample_count: int
    dt: float | None
    tt_range: tuple[float, float] | None
    fields: pd.DataFrame


def _numeric(values: np.ndarray, name: str) -> np.ndarray:
    try:
        if values.dtype.kind not in "iuf":
            raise ValueError("not a real numeric field")
        result = np.asarray(values, dtype=float)
        if not np.all(np.isfinite(result)):
            raise ValueError("non-finite values")
        return result
    except (TypeError, ValueError, OverflowError) as exc:
        raise DataIntegrityError(
            f"coordinate {name!r} must contain finite numbers"
        ) from exc


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    indexes = np.flatnonzero(mask)
    if not indexes.size:
        return []
    groups = np.split(indexes, np.flatnonzero(np.diff(indexes) != 1) + 1)
    return [(int(group[0]), int(group[-1]) + 1) for group in groups]


class _FileReader:
    """One open file; lazily load each coordinate once per read operation."""

    def __init__(self, handle: h5py.File, spec: FileSpec, catalog: Catalog) -> None:
        self.handle = handle
        self.spec = spec
        self.count = sample_count(handle)
        self.fields = sample_fields(
            handle, self.count, catalog.collection_fields(spec.collection)
        )

    @cached_property
    def source_coordinates(self) -> dict[str, np.ndarray]:
        return {
            name: np.asarray(self.fields[name][:])
            for name in IDENTITY_COLUMNS
            if name != "time" and name in self.fields
        }

    @cached_property
    def tt(self) -> np.ndarray:
        return _numeric(self.source_coordinates["tt"], "tt")

    @cached_property
    def lines(self) -> np.ndarray:
        values = _numeric(self.source_coordinates["line"], "line")
        if np.any(values < 0):
            raise DataIntegrityError("line coordinates cannot be negative")
        unique, inverse = np.unique(values, return_inverse=True)
        labels = np.asarray([f"{value:.2f}" for value in unique], dtype=object)
        return labels[inverse]

    @cached_property
    def identity(self) -> dict[str, Any]:
        date = pd.Timestamp(self.spec.date)
        defaults = {
            "flight": self.spec.flight,
            "year": date.year,
            "doy": date.dayofyear,
        }
        data: dict[str, Any] = {}
        for name, default in defaults.items():
            data[name] = (
                integer_values(self.source_coordinates[name], name)
                if name in self.fields
                else np.full(self.count, default, dtype=np.int64)
            )
        if np.any(data["flight"] != self.spec.flight):
            raise DataIntegrityError(
                f"flight identity does not match Flt{self.spec.flight}"
            )
        try:
            starts = pd.DatetimeIndex(
                pd.to_datetime(data["year"].astype(str), format="%Y", utc=True)
            )
            leap_year = pd.Series(starts).dt.is_leap_year.to_numpy()
            if np.any(data["doy"] < 1) or np.any(
                data["doy"] > np.where(leap_year, 366, 365)
            ):
                raise ValueError("invalid day of year")
            times = (
                starts
                + pd.to_timedelta(data["doy"] - 1, unit="D")
                + pd.to_timedelta(self.tt, unit="s")
            )
            # Give empty and nonempty outputs exactly the same datetime precision.
            times = pd.DatetimeIndex(times, dtype="datetime64[ns, UTC]")
        except (TypeError, ValueError, OverflowError) as exc:
            raise DataIntegrityError(
                f"invalid calendar coordinates in Flt{self.spec.flight}"
            ) from exc
        data.update(line=self.lines, tt=self.tt, time=times)
        return data

    def mask(self, selection: Selection) -> np.ndarray:
        mask = np.ones(self.count, dtype=bool)
        # Validate coordinates equally in normalized, raw, and empty reads.
        identity = self.identity
        if selection.lines is not None:
            mask &= np.isin(identity["line"], tuple(selection.lines))
        bounds = selection.tt if selection.tt is not None else selection.time
        if bounds is not None:
            values = identity["tt" if selection.tt is not None else "time"]
            if bounds.start is not None:
                mask &= values >= bounds.start
            if bounds.stop is not None:
                mask &= values < bounds.stop
        return mask

    def read(
        self,
        mask: np.ndarray,
        columns: tuple[str, ...],
        dtypes: dict[str, np.dtype],
        *,
        raw: bool,
    ) -> pd.DataFrame:
        runs = _runs(mask)
        count = int(mask.sum())
        data: dict[str, Any] = {}
        if not raw:
            for name in IDENTITY_COLUMNS:
                values = self.identity[name][mask]
                data[name] = (
                    pd.array(values, dtype="string") if name == "line" else values
                )
        for name in columns:
            if not raw and name in IDENTITY_COLUMNS:
                continue
            dtype = dtypes[name]
            if name not in self.fields:
                values = np.full(count, np.nan, dtype=dtype)
            elif not runs:
                values = np.empty(0, dtype=dtype)
            elif name in self.source_coordinates:
                values = self.source_coordinates[name][mask].astype(dtype, copy=False)
            else:
                field = self.fields[name]
                chunks = [np.asarray(field[start:stop]) for start, stop in runs]
                values = chunks[0] if len(chunks) == 1 else np.concatenate(chunks)
                values = values.astype(dtype, copy=False)
            data[name] = values
        return pd.DataFrame(data, index=pd.RangeIndex(count))


def _columns_and_dtypes(
    readers: dict[int, _FileReader],
    catalog: Catalog,
    columns: tuple[str, ...] | None,
    *,
    raw: bool,
    missing: str,
) -> tuple[tuple[str, ...], dict[str, np.dtype]]:
    actual = tuple(
        dict.fromkeys(name for reader in readers.values() for name in reader.fields)
    )
    names = actual if columns is None else columns
    dtypes = {}
    for name in names:
        if not raw and name in IDENTITY_COLUMNS:
            continue
        if (
            name not in actual
            and not catalog.known_field(name)
            and name not in IDENTITY_COLUMNS
        ):
            if any(name in reader.handle for reader in readers.values()):
                raise InvalidArgumentError(
                    f"{name!r} is not a one-dimensional sample field; "
                    "use fetch() for direct HDF5 access"
                )
            raise UnknownFieldError(
                f"unknown field {name!r}; inspect fields() or inspect(flight).fields"
            )
        malformed = [
            flight
            for flight, reader in readers.items()
            if name in reader.handle and name not in reader.fields
        ]
        if malformed:
            raise DataIntegrityError(
                f"field {name!r} has an invalid sample shape in flights {malformed}"
            )
        absent = [
            flight for flight, reader in readers.items() if name not in reader.fields
        ]
        if absent and missing == "raise":
            raise MissingFieldError(
                f"field {name!r} is missing in flights {absent}; "
                "use missing='fill' for NaN"
            )
        types = [
            reader.fields[name].dtype
            for reader in readers.values()
            if name in reader.fields
        ]
        if absent:
            types.append(
                np.dtype(float)
                if all(dtype.kind in "buifc" for dtype in types)
                else np.dtype(object)
            )
        try:
            dtypes[name] = np.result_type(*types)
        except TypeError:
            dtypes[name] = np.dtype(object)
    return names, dtypes


def _units(
    catalog: Catalog, specs: list[FileSpec], names: tuple[str, ...]
) -> dict[str, str]:
    result = {}
    for name in names:
        units = {
            str(catalog.field_metadata(name, spec.collection).get("units", ""))
            for spec in specs
        }
        units.discard("")
        if len(units) > 1:
            raise InvalidArgumentError(
                f"field {name!r} has conflicting units across "
                f"selected collections: {sorted(units)}"
            )
        if units:
            result[name] = units.pop()
    return result


def read_files(
    catalog: Catalog,
    specs: dict[int, FileSpec],
    paths: dict[int, Path],
    selections: tuple[Selection, ...],
    columns: tuple[str, ...] | None,
    *,
    raw: bool,
    missing: Literal["raise", "fill"],
    empty: Literal["raise", "allow"],
) -> tuple[pd.DataFrame, list[int]]:
    """Validate the full query schema, read samples, then concatenate in query order."""
    try:
        with ExitStack() as stack:
            readers = {
                flight: _FileReader(
                    stack.enter_context(h5py.File(paths[flight], "r")), spec, catalog
                )
                for flight, spec in specs.items()
            }
            names, dtypes = _columns_and_dtypes(
                readers, catalog, columns, raw=raw, missing=missing
            )
            output_names = (
                names if raw else tuple(dict.fromkeys((*IDENTITY_COLUMNS, *names)))
            )
            units = _units(catalog, list(specs.values()), output_names)
            frames, counts = [], []
            for index, selection in enumerate(selections, 1):
                reader = readers[selection.flight]
                mask = reader.mask(selection)
                count = int(mask.sum())
                if not count and empty == "raise":
                    raise NoDataError(
                        f"selection {index} contains no samples: {selection!r}"
                    )
                frames.append(reader.read(mask, names, dtypes, raw=raw))
                counts.append(count)
            result = pd.concat(frames, ignore_index=True, sort=False)
            result.attrs["units"] = units
            return result, counts
    except OSError as exc:
        raise DataIntegrityError(f"could not read HDF5 samples: {exc}") from exc


def inspect_file(path: Path, spec: FileSpec, catalog: Catalog) -> FlightInfo:
    try:
        with h5py.File(path, "r") as handle:
            reader = _FileReader(handle, spec, catalog)
            # Inspection also checks identity values, not only field shapes.
            _ = reader.identity
            rows = []
            for name, field in reader.fields.items():
                meta = catalog.field_metadata(name, spec.collection)
                rows.append(
                    {
                        "name": name,
                        "dtype": str(field.dtype),
                        **{
                            key: meta.get(key, "")
                            for key in ("units", "description", "group", "source_url")
                        },
                    }
                )
            return FlightInfo(
                flight=spec.flight,
                path=path,
                sample_count=reader.count,
                dt=sample_interval(handle),
                tt_range=(float(reader.tt.min()), float(reader.tt.max()))
                if reader.count
                else None,
                fields=pd.DataFrame(
                    rows,
                    columns=[
                        "name",
                        "dtype",
                        "units",
                        "description",
                        "group",
                        "source_url",
                    ],
                ),
            )
    except OSError as exc:
        raise DataIntegrityError(f"could not inspect HDF5 file {path}: {exc}") from exc
