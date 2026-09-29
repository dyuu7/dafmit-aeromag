from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import pooch

from ._hdf5 import SCALAR_FIELDS
from ._validation import field_names, flight_ids, ordered_values
from .catalog_core import Catalog
from .exceptions import InvalidArgumentError
from .reader import FlightInfo, inspect_file, read_files
from .selection import Selection
from .storage import FileStore


class Dataset:
    """Access one fixed release of the published flight files.

    Parameters
    ----------
    release:
        Bundled upstream release, currently ``"v3"`` (2020 and 2021 collections).
    data_dir:
        Download directory. Defaults to the user's dafmit-aeromag cache.
    progress:
        Show download progress bars.
    offline:
        Read local files only. Catalog discovery is always offline.

    Notes
    -----
    Files are verified on first use in this instance and after a change in their
    filesystem state. ``fetch(..., recheck=True)`` forces a fresh verification.
    No file handles remain open between calls. Configuration is read-only;
    create another Dataset to use different settings.
    """

    def __init__(
        self,
        release: str = "v3",
        *,
        data_dir: str | Path | None = None,
        progress: bool = True,
        offline: bool = False,
    ) -> None:
        if not isinstance(release, str):
            raise InvalidArgumentError("release must be a string")
        if not isinstance(progress, bool) or not isinstance(offline, bool):
            raise InvalidArgumentError("progress and offline must be booleans")
        if data_dir is not None and not isinstance(data_dir, (str, Path)):
            raise InvalidArgumentError("data_dir must be a string or Path")
        self._catalog = Catalog(release)
        directory = (
            Path(data_dir)
            if data_dir is not None
            else Path(pooch.os_cache("dafmit-aeromag"))
        )
        self._store = FileStore(
            directory.expanduser().resolve(), progress=progress, offline=offline
        )

    @property
    def release(self) -> str:
        """The fixed upstream release identifier."""
        return self._catalog.release

    @property
    def data_dir(self) -> Path:
        """Absolute directory used for downloaded or preexisting files."""
        return self._store.data_dir

    @property
    def offline(self) -> bool:
        """Whether missing local files are reported instead of downloaded."""
        return self._store.offline

    @property
    def progress(self) -> bool:
        """Whether file downloads display progress."""
        return self._store.progress

    @property
    def metadata(self) -> dict[str, Any]:
        """Detached release metadata and source links; never downloads files."""
        return self._catalog.metadata

    def __repr__(self) -> str:
        return (
            f"Dataset(release={self.release!r}, "
            f"data_dir={str(self.data_dir)!r}, offline={self.offline!r})"
        )

    def flights(self, *, collection: str | None = None) -> pd.DataFrame:
        """List published files, dates, sizes, checksums, and flight notes."""
        return self._catalog.flights_frame(collection)

    def fields(
        self,
        *,
        flight: int | None = None,
        collection: str | None = None,
        group: str | None = None,
    ) -> pd.DataFrame:
        """List upstream field definitions without downloading a file.

        Supply either flight or collection to restrict definitions to one year.
        A definition does not guarantee physical presence in every flight file;
        use ``inspect(flight).fields`` to discover actual sample fields.
        """
        return self._catalog.fields_frame(flight, collection, group)

    def field_names(
        self,
        *,
        flight: int | None = None,
        collection: str | None = None,
        group: str | None = None,
    ) -> tuple[str, ...]:
        """Return ordered, unique names from the same query as ``fields()``."""
        return tuple(
            dict.fromkeys(
                self.fields(flight=flight, collection=collection, group=group)["name"]
            )
        )

    def field_groups(
        self, *, flight: int | None = None, collection: str | None = None
    ) -> pd.DataFrame:
        """Summarize groups by name, description, and number of unique fields."""
        return self._catalog.field_groups_frame(flight, collection)

    def sensors(
        self, *, flight: int | None = None, collection: str | None = None
    ) -> pd.DataFrame:
        """List documented sensor positions for one collection or all collections."""
        return self._catalog.sensors_frame(flight, collection)

    def segments(self, flights: int | Iterable[int] | None = None) -> pd.DataFrame:
        """List documented segments, including upstream holdout annotations.

        ``is_holdout`` only reports an upstream annotation. It does not claim
        that samples are available or assign samples to a training/test split.
        Recorded start/end times are preserved as documentation, not read masks.
        """
        return self._catalog.segments_frame(flights)

    def fetch(
        self, flights: int | Iterable[int], *, recheck: bool = False
    ) -> dict[int, Path]:
        """Ensure files are verified locally and return ``{flight: path}``.

        ``recheck=True`` forces checksum and structure verification even if the
        file has not changed since its previous verification in this instance.
        """
        if not isinstance(recheck, bool):
            raise InvalidArgumentError("recheck must be a boolean")
        specs = [self._catalog.file_spec(flight) for flight in flight_ids(flights)]
        return {spec.flight: self._store.fetch(spec, recheck=recheck) for spec in specs}

    def inspect(self, flight: int) -> FlightInfo:
        """Inspect actual sample fields and coverage, downloading if necessary."""
        spec = self._catalog.file_spec(flight)
        path = self._store.fetch(spec)
        info = inspect_file(path, spec, self._catalog)
        self._store.check_unchanged([path])
        return info

    def read(
        self,
        selections: Selection | Iterable[Selection],
        *,
        columns: str | Iterable[str],
        raw: bool = False,
        missing: Literal["raise", "fill"] = "raise",
        empty: Literal["raise", "allow"] = "raise",
    ) -> pd.DataFrame:
        """Read file samples matching explicit selections, preserving their order.

        Parameters
        ----------
        selections:
            One Selection or an ordered iterable. Overlapping selections retain
            duplicate samples. Source row order is preserved within each selection.
        columns:
            A name, ordered iterable of names, or ``"all"`` for the union of
            actual sample fields. An empty iterable requests identity columns only.
        raw:
            Return source fields only, without normalized identity columns.
            Raw reads cannot request derived ``time`` or an empty column list.
        missing:
            ``"raise"`` rejects absent fields; ``"fill"`` supplies NaN. Neither
            option accepts malformed fields or unknown names.
        empty:
            ``"raise"`` rejects any selection without samples. ``"allow"``
            permits empty selections, including a fully empty result with a schema.

        Returns
        -------
        pandas.DataFrame
            Normalized frames start with flight, line, year, doy, tt, time.
            Time is UTC. Metadata in ``attrs`` records provenance, units, and
            each selection's row count. Upstream holdout notes never filter rows.
        """
        query = (
            (selections,)
            if isinstance(selections, Selection)
            else ordered_values(selections, "selections")
        )
        if not query or any(not isinstance(item, Selection) for item in query):
            raise InvalidArgumentError("selections must contain at least one Selection")
        if not isinstance(raw, bool):
            raise InvalidArgumentError("raw must be a boolean")
        if not isinstance(missing, str) or missing not in ("raise", "fill"):
            raise InvalidArgumentError("missing must be 'raise' or 'fill'")
        if not isinstance(empty, str) or empty not in ("raise", "allow"):
            raise InvalidArgumentError("empty must be 'raise' or 'allow'")
        names = (
            None
            if isinstance(columns, str) and columns == "all"
            else field_names(columns)
        )
        if names is not None:
            if set(names) & SCALAR_FIELDS:
                raise InvalidArgumentError(
                    "N, dt, and info are scalar metadata; use inspect() or fetch()"
                )
            if raw and (not names or "time" in names):
                raise InvalidArgumentError(
                    "raw reads require source fields; "
                    "derived 'time' and empty columns are unsupported"
                )
        specs = {
            flight: self._catalog.file_spec(flight)
            for flight in dict.fromkeys(item.flight for item in query)
        }
        paths = {flight: self._store.fetch(spec) for flight, spec in specs.items()}
        frame, counts = read_files(
            self._catalog,
            specs,
            paths,
            query,
            names,
            raw=raw,
            missing=missing,
            empty=empty,
        )
        self._store.check_unchanged(list(paths.values()))
        metadata = self.metadata
        frame.attrs.update(
            release=self.release,
            doi=metadata.get("doi"),
            record_id=metadata.get("record_id"),
            raw=raw,
            flights=list(specs),
            selections=[
                {
                    "flight": selection.flight,
                    "lines": list(selection.lines)
                    if selection.lines is not None
                    else None,
                    "tt": [selection.tt.start, selection.tt.stop]
                    if selection.tt is not None
                    else None,
                    "time": [
                        bound.isoformat() if bound is not None else None
                        for bound in (selection.time.start, selection.time.stop)
                    ]
                    if selection.time is not None
                    else None,
                    "row_count": count,
                }
                for selection, count in zip(query, counts, strict=True)
            ],
        )
        return frame
