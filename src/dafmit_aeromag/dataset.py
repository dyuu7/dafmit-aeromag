"""The public dataset interface and efficient HDF5 reader."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from numbers import Integral
from pathlib import Path
from typing import Any, Literal, cast

import h5py
import numpy as np
import pandas as pd
import pooch

from .catalog_core import Catalog
from .exceptions import (
    DataIntegrityError,
    InvalidSelectionError,
    MissingFieldError,
    NoDataError,
    UnknownFieldError,
)
from .selection import Selection
from .storage import resolve_file

_IDENTITY_COLUMNS = ("flight", "line", "year", "doy", "tt", "time")
_SCALAR_FIELDS = {"N", "dt", "info"}
_SPLITS = {"train", "holdout", "all"}


def _normalise_split(value: str) -> Literal["train", "holdout", "all"]:
    if value not in _SPLITS:
        raise ValueError("split must be 'train', 'holdout', or 'all'")
    return cast(Literal["train", "holdout", "all"], value)


def _normalise_flights(value: int | Iterable[int]) -> tuple[int, ...]:
    if isinstance(value, bool):
        raise InvalidSelectionError("flight identifiers must be integers")
    if isinstance(value, Integral) and not isinstance(value, bool):
        values = (int(value),)
    elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        values = tuple(value)
    else:
        raise InvalidSelectionError(
            "flights must be an integer or an iterable of integers"
        )
    if not values:
        raise InvalidSelectionError("flights cannot be empty")
    result: list[int] = []
    for flight in values:
        if isinstance(flight, bool) or not isinstance(flight, Integral):
            raise InvalidSelectionError("flight identifiers must be integers")
        normalized = int(flight)
        if normalized not in result:
            result.append(normalized)
    return tuple(result)


def _normalise_columns(
    columns: Sequence[str] | str,
) -> tuple[bool, tuple[str, ...]]:
    if isinstance(columns, str) and columns == "all":
        return True, ()
    if isinstance(columns, str):
        raise InvalidSelectionError(
            "columns must be 'all' or an explicit sequence of names"
        )
    if not isinstance(columns, Sequence):
        raise InvalidSelectionError(
            "columns must be 'all' or an explicit sequence of names"
        )
    result: list[str] = []
    for name in columns:
        if not isinstance(name, str) or not name:
            raise InvalidSelectionError("column names must be non-empty strings")
        if name not in result:
            result.append(name)
    if not result:
        raise InvalidSelectionError("columns cannot be empty")
    return False, tuple(result)


def _contiguous_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    indexes = np.flatnonzero(mask)
    if indexes.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(indexes) != 1) + 1
    groups = np.split(indexes, breaks)
    return [(int(group[0]), int(group[-1]) + 1) for group in groups]


def _line_label(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidSelectionError(
            f"line dataset contains a non-numeric value: {value!r}"
        ) from exc
    if not np.isfinite(number):
        raise InvalidSelectionError("line dataset contains a non-finite value")
    return f"{number:.2f}"


def _timestamp(value: Any) -> pd.Timestamp:
    try:
        result = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidSelectionError(f"invalid time bound {value!r}") from exc
    if result.tzinfo is None:
        return cast(pd.Timestamp, result.tz_localize("UTC"))
    return cast(pd.Timestamp, result.tz_convert("UTC"))


def _as_integer(values: np.ndarray, name: str) -> np.ndarray:
    """Convert numeric identity values without silently accepting fractions."""

    array = np.asarray(values)
    try:
        numeric = array.astype(float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MissingFieldError(
            f"identity field {name!r} contains invalid values"
        ) from exc
    if not np.all(np.isfinite(numeric)) or not np.all(numeric == np.floor(numeric)):
        raise MissingFieldError(f"identity field {name!r} contains invalid values")
    return numeric.astype(np.int64)


def _dataset(handle: h5py.File, name: str) -> h5py.Dataset | None:
    value = handle.get(name)
    return value if isinstance(value, h5py.Dataset) else None


class Dataset:
    """Query a fixed, reproducible release of the open flight data.

    Parameters
    ----------
    release:
        Bundled catalog release. Version ``"v3"`` contains the 2020 and 2021
        collections.
    data_dir:
        Directory for downloaded HDF5 files. By default Pooch's user cache is
        used.
    progress:
        Show download progress bars when a file is fetched.
    offline:
        Refuse downloads and use only already verified local files.
    """

    def __init__(
        self,
        release: str = "v3",
        *,
        data_dir: str | Path | None = None,
        progress: bool = True,
        offline: bool = False,
    ) -> None:
        self.catalog = Catalog(release)
        self.release = release
        self.data_dir = (
            Path(data_dir)
            if data_dir is not None
            else Path(pooch.os_cache("dafmit-aeromag"))
        )
        self.progress = progress
        self.offline = offline

    def __repr__(self) -> str:
        return (
            f"Dataset(release={self.release!r}, data_dir={str(self.data_dir)!r}, "
            f"offline={self.offline!r})"
        )

    def flights(self, collection: str | None = None) -> pd.DataFrame:
        """Return the release's flight/file catalog as a DataFrame."""

        frame = self.catalog.flights_frame()
        if collection is not None:
            self.catalog._validate_collection(collection)
            frame = frame.loc[frame["collection"] == collection].reset_index(drop=True)
        return frame

    def fields(
        self,
        flight: int | None = None,
        *,
        collection: str | None = None,
        group: str | None = None,
    ) -> pd.DataFrame:
        """Return field names, units, descriptions, and collection coverage."""

        return self.catalog.fields_frame(flight, collection, group)

    def field_groups(
        self,
        group: str | None = None,
        *,
        flight: int | None = None,
        collection: str | None = None,
    ) -> pd.DataFrame:
        """Return fields organized by stable convenience groups.

        Groups are a navigation aid only; the ``name`` column remains the
        original HDF5 field name.
        """

        return self.catalog.field_groups_frame(group, flight, collection)

    def field_names(
        self,
        group: str,
        *,
        flight: int | None = None,
        collection: str | None = None,
    ) -> tuple[str, ...]:
        """Return original HDF5 field names in a convenience group."""

        return self.catalog.field_names(
            group,
            flight=flight,
            collection=collection,
        )

    def sensors(self, collection: str | None = None) -> pd.DataFrame:
        """Return documented magnetometer and fluxgate sensor positions."""

        return self.catalog.sensors_frame(collection)

    def segments(
        self,
        flights: int | Iterable[int] | None = None,
        *,
        split: str | None = None,
        flight: int | None = None,
    ) -> pd.DataFrame:
        """Return documented flight segments, including holdout metadata."""

        if flight is not None:
            if flights is not None:
                raise InvalidSelectionError("use either flight or flights, not both")
            flights = flight
        return self.catalog.segments_frame(flights, split)

    def _get_path(self, flight: int) -> Path:
        return resolve_file(
            self.catalog.file_spec(flight),
            data_dir=self.data_dir,
            progress=self.progress,
            offline=self.offline,
        )

    def fetch(self, flights: int | Iterable[int]) -> dict[int, Path]:
        """Ensure files are local and return ``{flight: path}``."""

        result: dict[int, Path] = {}
        for flight in _normalise_flights(flights):
            result[flight] = self._get_path(flight)
        return result

    def _measurement_columns(
        self,
        selections: tuple[Selection, ...],
        all_columns: bool,
        explicit: tuple[str, ...],
    ) -> tuple[str, ...]:
        if not all_columns:
            for name in explicit:
                if name == "time":
                    raise UnknownFieldError(
                        "'time' is a normalized output coordinate; "
                        "it is not a source field"
                    )
                if name not in _IDENTITY_COLUMNS:
                    self.catalog.field_metadata(name)
            return explicit
        return ()

    def _validate_missing(
        self,
        selections: tuple[Selection, ...],
        columns: tuple[str, ...],
        *,
        missing: str,
        all_columns: bool,
    ) -> None:
        if missing not in {"raise", "fill"}:
            raise ValueError("missing must be 'raise' or 'fill'")
        if missing == "fill":
            return
        if all_columns:
            return
        for selection in selections:
            spec = self.catalog.file_spec(selection.flight)
            available = set(self.catalog.collection_fields(spec.collection))
            absent = [
                name
                for name in columns
                if name not in _IDENTITY_COLUMNS and name not in available
            ]
            if absent:
                raise MissingFieldError(
                    f"fields unavailable in flight {selection.flight}: "
                    f"{', '.join(absent)}; "
                    "use missing='fill' to receive NaN columns"
                )

    @staticmethod
    def _actual_sample_columns(paths: dict[int, Path]) -> tuple[str, ...]:
        """Return the union of one-dimensional fields physically stored in files."""

        names: list[str] = []
        for path in paths.values():
            with h5py.File(path, "r") as handle:
                for name, dataset in handle.items():
                    if (
                        isinstance(dataset, h5py.Dataset)
                        and dataset.ndim == 1
                        and name not in names
                    ):
                        names.append(name)
        return tuple(name for name in names if name not in _SCALAR_FIELDS)

    def read(
        self,
        selections: Selection | Sequence[Selection],
        *,
        columns: Sequence[str] | str,
        split: str = "train",
        raw: bool = False,
        missing: str = "raise",
    ) -> pd.DataFrame:
        """Read one or more selections into a single DataFrame.

        Selection order is preserved, followed by source row order. The
        normalized output always starts with ``flight, line, year, doy, tt,
        time``. By default only catalogued training intervals are returned;
        pass ``split='holdout'`` or ``split='all'`` to choose another view.
        ``raw=True`` returns only the requested source sample fields.
        """

        if isinstance(selections, Selection):
            query = (selections,)
        else:
            try:
                query = tuple(selections)
            except TypeError as exc:
                raise InvalidSelectionError(
                    "selections must be a Selection or a sequence of Selection objects"
                ) from exc
        if not query or any(not isinstance(item, Selection) for item in query):
            raise InvalidSelectionError(
                "selections must contain at least one Selection"
            )
        selected_split = _normalise_split(split)
        all_columns, explicit = _normalise_columns(columns)
        measurement_columns = self._measurement_columns(query, all_columns, explicit)
        self._validate_missing(
            query,
            measurement_columns,
            missing=missing,
            all_columns=all_columns,
        )

        paths = self.fetch(tuple(item.flight for item in query))
        if all_columns:
            measurement_columns = self._actual_sample_columns(paths)
        frames = [
            self._read_one(
                selection,
                paths[selection.flight],
                measurement_columns,
                split=selected_split,
                raw=raw,
                missing=missing,
            )
            for selection in query
        ]
        result = pd.concat(frames, ignore_index=True, sort=False)
        result.attrs.update(
            {
                "release": self.release,
                "doi": self.catalog.metadata.get("doi"),
                "record_id": self.catalog.metadata.get("record_id"),
                "raw": raw,
                "split": selected_split,
                "flights": [item.flight for item in query],
                "units": {
                    name: self.catalog.field_metadata(name).get("units", "")
                    for name in measurement_columns
                    if self.catalog.known_field(name)
                },
            }
        )
        return result

    @staticmethod
    def _sample_length(handle: h5py.File) -> int:
        line = _dataset(handle, "line")
        tt = _dataset(handle, "tt")
        if line is None or tt is None:
            raise MissingFieldError(
                "HDF5 file must contain one-dimensional 'line' and 'tt' fields"
            )
        if line.ndim != 1 or tt.ndim != 1 or line.shape != tt.shape:
            raise MissingFieldError(
                "HDF5 'line' and 'tt' datasets must have the same sample shape"
            )
        count = int(line.shape[0])
        declared = _dataset(handle, "N")
        if declared is not None:
            if declared.ndim != 0:
                raise DataIntegrityError("HDF5 'N' metadata must be scalar")
            try:
                declared_count = int(declared[()])
            except (TypeError, ValueError, OverflowError) as exc:
                raise DataIntegrityError("HDF5 'N' metadata is not an integer") from exc
            if declared_count != count:
                raise DataIntegrityError(
                    f"HDF5 'N' metadata ({declared_count}) does not match "
                    f"sample count ({count})"
                )
        return count

    @staticmethod
    def _read_runs(
        handle: h5py.File,
        name: str,
        runs: list[tuple[int, int]],
        *,
        missing: str,
    ) -> np.ndarray:
        count = sum(stop - start for start, stop in runs)
        dataset = _dataset(handle, name)
        line = _dataset(handle, "line")
        if (
            dataset is None
            or line is None
            or dataset.ndim != 1
            or dataset.shape[0] != line.shape[0]
        ):
            if missing == "fill":
                return np.full(count, np.nan)
            raise MissingFieldError(
                f"field {name!r} is absent or is not a one-dimensional sample field"
            )
        chunks = [np.asarray(dataset[start:stop]) for start, stop in runs]
        return np.concatenate(chunks) if len(chunks) > 1 else chunks[0]

    @staticmethod
    def _identity_values(
        handle: h5py.File,
        name: str,
        runs: list[tuple[int, int]],
        *,
        flight: int,
        date: str,
        missing: str,
    ) -> np.ndarray:
        dataset = _dataset(handle, name)
        if dataset is not None:
            if dataset.ndim != 1:
                raise DataIntegrityError(
                    f"HDF5 identity field {name!r} is not one-dimensional"
                )
            values = Dataset._read_runs(handle, name, runs, missing=missing)
            if name == "flight":
                identities = _as_integer(values, name)
                if not np.all(identities == flight):
                    raise DataIntegrityError(
                        f"HDF5 flight identity does not match Flt{flight}"
                    )
            return values
        count = sum(stop - start for start, stop in runs)
        timestamp = pd.Timestamp(date)
        if name == "flight":
            return np.full(count, flight, dtype=np.int64)
        if name == "year":
            return np.full(count, timestamp.year, dtype=np.int64)
        if name == "doy":
            return np.full(count, timestamp.dayofyear, dtype=np.int64)
        raise MissingFieldError(f"cannot derive identity field {name!r}")

    def _time_values(
        self,
        handle: h5py.File,
        runs: list[tuple[int, int]],
        *,
        flight: int,
        date: str,
        tt: np.ndarray,
    ) -> pd.DatetimeIndex:
        if _dataset(handle, "year") is not None or _dataset(handle, "doy") is not None:
            years = _as_integer(
                self._identity_values(
                    handle, "year", runs, flight=flight, date=date, missing="raise"
                ),
                "year",
            )
            doys = _as_integer(
                self._identity_values(
                    handle, "doy", runs, flight=flight, date=date, missing="raise"
                ),
                "doy",
            )
            starts = pd.to_datetime(years.astype(str), format="%Y", utc=True)
            return (
                pd.DatetimeIndex(starts)
                + pd.to_timedelta(doys - 1, unit="D")
                + pd.to_timedelta(tt, unit="s")
            )
        start = pd.Timestamp(date, tz="UTC")
        return pd.DatetimeIndex(start + pd.to_timedelta(tt, unit="s"))

    def _selection_mask(
        self,
        handle: h5py.File,
        selection: Selection,
        *,
        date: str,
        split: Literal["train", "holdout", "all"],
    ) -> tuple[np.ndarray, np.ndarray]:
        n = self._sample_length(handle)
        line = _dataset(handle, "line")
        tt = _dataset(handle, "tt")
        if line is None or tt is None:  # validated again for static type narrowing
            raise MissingFieldError("HDF5 file must contain 'line' and 'tt' datasets")
        line_values = np.asarray(line[:])
        try:
            tt_values = np.asarray(tt[:], dtype=float)
        except (TypeError, ValueError, OverflowError) as exc:
            raise DataIntegrityError("HDF5 'tt' contains non-numeric values") from exc
        mask = np.ones(n, dtype=bool)
        if selection.lines is not None:
            labels = np.asarray(
                [_line_label(value) for value in line_values], dtype=object
            )
            mask &= np.isin(labels, selection.lines)
        if selection.tt is not None:
            if selection.tt.start is not None:
                mask &= tt_values >= selection.tt.start
            if selection.tt.stop is not None:
                mask &= tt_values < selection.tt.stop
        if selection.time is not None:
            times = self._time_values(
                handle,
                [(0, n)],
                flight=selection.flight,
                date=date,
                tt=tt_values,
            )
            if selection.time.start is not None:
                mask &= times >= _timestamp(selection.time.start)
            if selection.time.stop is not None:
                mask &= times < _timestamp(selection.time.stop)
        if split != "all":
            holdout = np.zeros(n, dtype=bool)
            for start, stop in self.catalog.holdout_intervals(selection.flight):
                holdout |= (tt_values >= start) & (tt_values < stop)
            if split == "train":
                mask &= ~holdout
            else:
                mask &= holdout
        return mask, tt_values

    def _read_one(
        self,
        selection: Selection,
        path: Path,
        columns: tuple[str, ...],
        *,
        split: Literal["train", "holdout", "all"],
        raw: bool,
        missing: str,
    ) -> pd.DataFrame:
        spec = self.catalog.file_spec(selection.flight)
        with h5py.File(path, "r") as handle:
            mask, _ = self._selection_mask(
                handle,
                selection,
                date=spec.date,
                split=split,
            )
            runs = _contiguous_runs(mask)
            if not runs:
                raise NoDataError(
                    f"selection for flight {selection.flight} contains no samples "
                    f"for split {split!r}"
                )
            if raw:
                data = {
                    name: self._read_runs(handle, name, runs, missing=missing)
                    for name in columns
                    if name != "time"
                }
                return pd.DataFrame(data)

            tt = self._read_runs(handle, "tt", runs, missing="raise").astype(float)
            line = self._read_runs(handle, "line", runs, missing="raise")
            data: dict[str, Any] = {
                "flight": _as_integer(
                    self._identity_values(
                        handle,
                        "flight",
                        runs,
                        flight=selection.flight,
                        date=spec.date,
                        missing="raise",
                    ),
                    "flight",
                ),
                "line": np.asarray(
                    [_line_label(value) for value in line], dtype=object
                ),
                "year": _as_integer(
                    self._identity_values(
                        handle,
                        "year",
                        runs,
                        flight=selection.flight,
                        date=spec.date,
                        missing="raise",
                    ),
                    "year",
                ),
                "doy": _as_integer(
                    self._identity_values(
                        handle,
                        "doy",
                        runs,
                        flight=selection.flight,
                        date=spec.date,
                        missing="raise",
                    ),
                    "doy",
                ),
                "tt": tt,
            }
            data["time"] = self._time_values(
                handle,
                runs,
                flight=selection.flight,
                date=spec.date,
                tt=tt,
            )
            for name in columns:
                if name not in _IDENTITY_COLUMNS:
                    data[name] = self._read_runs(handle, name, runs, missing=missing)
            ordered = ["flight", "line", "year", "doy", "tt", "time"]
            ordered.extend(name for name in columns if name not in _IDENTITY_COLUMNS)
            return pd.DataFrame(data, columns=ordered)

    def to_xarray(self, frame: pd.DataFrame) -> Any:
        """Convert a DataFrame returned by :meth:`read` to an xarray Dataset."""

        try:
            import xarray as xr
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise ImportError(
                "xarray support is optional; install 'dafmit-aeromag[xarray]'"
            ) from exc
        coords: dict[str, Any] = {"sample": np.arange(len(frame), dtype=np.int64)}
        data_vars: dict[str, Any] = {}
        for name in frame.columns:
            target = coords if name in _IDENTITY_COLUMNS else data_vars
            target[name] = ("sample", frame[name].to_numpy())
        dataset = xr.Dataset(data_vars=data_vars, coords=coords)
        dataset.attrs.update(frame.attrs)
        units = frame.attrs.get("units", {})
        for name, unit in units.items():
            if name in dataset:
                dataset[name].attrs["units"] = unit
        return dataset
