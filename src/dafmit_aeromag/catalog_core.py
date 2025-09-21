"""Read-only access to the package's versioned release catalog."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from numbers import Integral
from typing import Any, cast

import pandas as pd

from .exceptions import UnknownFieldError, UnknownFlightError, UnknownReleaseError


@dataclass(frozen=True, slots=True)
class FileSpec:
    flight: int
    collection: str
    date: str
    file: str
    url: str
    size_bytes: int
    checksum: str
    dt: float
    has_holdout: bool


def _load_json(release: str) -> dict[str, Any]:
    if release != "v3":
        raise UnknownReleaseError(
            f"unknown release {release!r}; this package currently bundles only 'v3'"
        )
    resource = files("dafmit_aeromag.catalog").joinpath(f"{release}.json")
    try:
        return json.loads(resource.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:  # pragma: no cover - packaging failure
        raise UnknownReleaseError(f"catalog file for {release!r} is missing") from exc


@cache
def _catalog_data(release: str) -> dict[str, Any]:
    return _load_json(release)


class Catalog:
    """A validated, immutable view over one bundled release."""

    def __init__(self, release: str = "v3") -> None:
        self.release = release
        self._data = _catalog_data(release)
        self._flights = {int(item["flight"]): item for item in self._data["flights"]}
        self._fields = list(self._data["fields"])
        self._field_names = {item["name"] for item in self._fields}
        self._sensors = list(self._data.get("sensor_layout", []))
        self._segments = list(self._data["segments"])

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self._data.items()
            if key not in {"flights", "fields", "segments"}
        }

    def require_flight(self, flight: int) -> dict[str, Any]:
        if isinstance(flight, bool) or not isinstance(flight, Integral):
            raise UnknownFlightError(f"flight {flight!r} is not an integer identifier")
        flight = int(flight)
        try:
            return self._flights[flight]
        except KeyError as exc:
            raise UnknownFlightError(
                f"flight {flight!r} is not in release {self.release}"
            ) from exc

    def file_spec(self, flight: int) -> FileSpec:
        item = self.require_flight(flight)
        return FileSpec(
            flight=int(item["flight"]),
            collection=str(item["collection"]),
            date=str(item["date"]),
            file=str(item["file"]),
            url=str(item["url"]),
            size_bytes=int(item["size_bytes"]),
            checksum=str(item["checksum"]),
            dt=float(item["dt"]),
            has_holdout=bool(item["has_holdout"]),
        )

    def collection_fields(self, collection: str) -> tuple[str, ...]:
        return tuple(
            item["name"] for item in self._fields if item["collection"] == collection
        )

    def field_metadata(
        self, name: str, collection: str | None = None
    ) -> dict[str, Any]:
        matches = [
            item
            for item in self._fields
            if item["name"] == name
            and (collection is None or item["collection"] == collection)
        ]
        if not matches:
            raise UnknownFieldError(
                f"unknown field {name!r}; inspect Dataset.fields() for the catalog"
            )
        return matches[0]

    def known_field(self, name: str) -> bool:
        return name in self._field_names

    def flights_frame(self) -> pd.DataFrame:
        columns = [
            "flight",
            "collection",
            "date",
            "file",
            "size_bytes",
            "checksum",
            "dt",
            "has_holdout",
            "notes",
            "source_url",
        ]
        rows = [
            {
                **{key: item[key] for key in columns if key in item},
                "notes": tuple(item.get("notes", [])),
                "source_url": item.get("source_url", ""),
            }
            for item in self._flights.values()
        ]
        return pd.DataFrame(rows)

    def fields_frame(
        self,
        flight: int | None = None,
        collection: str | None = None,
        group: str | None = None,
    ) -> pd.DataFrame:
        self._validate_collection(collection)
        self._validate_group(group)
        columns = [
            "name",
            "units",
            "description",
            "collection",
            "group",
            "notes",
            "source_url",
        ]
        if flight is None:
            rows = [self._field_row(item) for item in self._fields]
        else:
            flight_collection = self.require_flight(flight)["collection"]
            if collection is not None and collection != flight_collection:
                return pd.DataFrame(columns=[*columns, "available"])
            rows = [
                {
                    **self._field_row(item),
                    "available": item["collection"] == flight_collection,
                }
                for item in self._fields
            ]
        if collection is not None:
            rows = [item for item in rows if item["collection"] == collection]
        if group is not None:
            rows = [item for item in rows if item["group"] == group]
        output_columns = [*columns, "available"] if flight is not None else columns
        return pd.DataFrame(rows, columns=output_columns)

    @staticmethod
    def _validate_collection(collection: str | None) -> None:
        if collection is not None and collection not in {"2020", "2021"}:
            raise ValueError("collection must be '2020' or '2021'")

    def _validate_group(self, group: str | None) -> None:
        if group is not None and group not in {
            str(item.get("group", "")) for item in self._fields
        }:
            raise ValueError(f"unknown field group {group!r}")

    @staticmethod
    def _field_row(item: dict[str, Any]) -> dict[str, Any]:
        return {
            **item,
            "group": item.get("group", "navigation"),
            "notes": tuple(item.get("notes", [])),
            "source_url": item.get("source_url", ""),
        }

    def field_names(
        self,
        group: str,
        *,
        flight: int | None = None,
        collection: str | None = None,
    ) -> tuple[str, ...]:
        """Return source field names in a stable convenience group."""

        frame = self.fields_frame(flight, collection, group)
        if flight is not None:
            frame = frame.loc[frame["available"]]
        return tuple(frame["name"].tolist())

    def field_groups_frame(
        self,
        group: str | None = None,
        flight: int | None = None,
        collection: str | None = None,
    ) -> pd.DataFrame:
        """Return field metadata with the convenience group first."""

        frame = self.fields_frame(flight, collection, group)
        columns = ["group", *[name for name in frame.columns if name != "group"]]
        return frame.loc[:, columns]

    def sensors_frame(self, collection: str | None = None) -> pd.DataFrame:
        """Return the documented magnetometer and fluxgate layout."""

        self._validate_collection(collection)
        rows = [
            dict(item)
            for item in self._sensors
            if collection is None or item["collection"] == collection
        ]
        columns = [
            "collection",
            "sensor",
            "description",
            "x",
            "y",
            "z",
            "source_url",
        ]
        return pd.DataFrame(rows, columns=columns)

    def segments_frame(
        self,
        flights: int | Iterable[int] | None = None,
        split: str | None = None,
    ) -> pd.DataFrame:
        if flights is None:
            allowed = None
        elif isinstance(flights, bool):
            raise UnknownFlightError("flights must be integer identifiers")
        elif isinstance(flights, Integral):
            flight = int(flights)
            self.require_flight(flight)
            allowed = {flight}
        else:
            try:
                requested = tuple(cast(Iterable[int], flights))
            except TypeError as exc:
                raise UnknownFlightError("flights must be integer identifiers") from exc
            allowed = set()
            for flight in requested:
                self.require_flight(flight)
                allowed.add(flight)
        if split is not None and split not in {"train", "holdout"}:
            raise ValueError("split must be 'train' or 'holdout'")
        rows = [
            dict(item)
            for item in self._segments
            if (allowed is None or int(item["flight"]) in allowed)
            and (split is None or item["split"] == split)
        ]
        columns = [
            "flight",
            "segment",
            "line",
            "start_tt",
            "end_tt",
            "description",
            "split",
            "released",
        ]
        return pd.DataFrame(rows, columns=columns)

    def holdout_intervals(self, flight: int) -> tuple[tuple[float, float], ...]:
        """Return native-time intervals that are marked as unreleased."""

        self.require_flight(flight)
        return tuple(
            (float(item["start_tt"]), float(item["end_tt"]))
            for item in self._segments
            if item["flight"] == flight and item["split"] == "holdout"
        )
