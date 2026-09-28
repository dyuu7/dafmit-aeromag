"""Internal access to the bundled release catalog; no file downloads."""

from __future__ import annotations

import json
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import Any

import pandas as pd

from ._validation import flight_id, flight_ids
from .exceptions import InvalidArgumentError, UnknownFlightError, UnknownReleaseError

GROUP_DESCRIPTIONS = {
    "identity": "Flight, line, and time identifiers",
    "navigation": "Position, altitude, and terrain information",
    "scalar_magnetometer": "Scalar magnetic measurements and corrections",
    "fluxgate": "Vector magnetic measurements",
    "ins": "Inertial navigation, attitude, velocity, and acceleration",
    "current": "Electrical current measurements",
    "voltage": "Electrical voltage measurements",
    "avionics": "Aircraft motion and air data measurements",
    "reference": "Reference measurements",
}


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


@cache
def _catalog_data(release: str) -> dict[str, Any]:
    if release != "v3":
        raise UnknownReleaseError(
            f"unknown release {release!r}; this package bundles 'v3'"
        )
    resource = files("dafmit_aeromag.catalog").joinpath(f"{release}.json")
    try:
        return json.loads(resource.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UnknownReleaseError(f"catalog file for {release!r} is missing") from exc


class Catalog:
    """Own a private snapshot of the release and return detached query results."""

    def __init__(self, release: str) -> None:
        self.release = release
        self._data = deepcopy(_catalog_data(release))
        self._flights = {item["flight"]: item for item in self._data["flights"]}
        self._fields = self._data["fields"]
        self._by_field = {
            (item["collection"], item["name"]): item for item in self._fields
        }

    @property
    def metadata(self) -> dict[str, Any]:
        tables = {"flights", "fields", "segments", "sensor_layout"}
        return deepcopy(
            {key: value for key, value in self._data.items() if key not in tables}
        )

    def require_flight(self, flight: int) -> dict[str, Any]:
        flight = flight_id(flight)
        if flight not in self._flights:
            raise UnknownFlightError(
                f"flight {flight} is not in release {self.release}"
            )
        return deepcopy(self._flights[flight])

    def file_spec(self, flight: int) -> FileSpec:
        item = self.require_flight(flight)
        return FileSpec(**{key: item[key] for key in FileSpec.__dataclass_fields__})

    def resolve_collection(
        self, flight: int | None, collection: str | None
    ) -> str | None:
        if flight is not None and collection is not None:
            raise InvalidArgumentError("use either flight or collection, not both")
        if flight is not None:
            return str(self.require_flight(flight)["collection"])
        collections = {item["collection"] for item in self._flights.values()}
        if collection is not None and (
            not isinstance(collection, str) or collection not in collections
        ):
            raise InvalidArgumentError(
                f"unknown collection {collection!r}; choose {sorted(collections)}"
            )
        return collection

    def flights_frame(self, collection: str | None) -> pd.DataFrame:
        collection = self.resolve_collection(None, collection)
        columns = [
            "flight",
            "collection",
            "date",
            "file",
            "size_bytes",
            "checksum",
            "dt",
            "notes",
            "source_url",
        ]
        rows = [
            item
            for item in self._flights.values()
            if collection is None or item["collection"] == collection
        ]
        return pd.DataFrame(deepcopy(rows), columns=columns)

    def fields_frame(
        self, flight: int | None, collection: str | None, group: str | None
    ) -> pd.DataFrame:
        collection = self.resolve_collection(flight, collection)
        if group is not None and (
            not isinstance(group, str) or group not in GROUP_DESCRIPTIONS
        ):
            raise InvalidArgumentError(
                f"unknown field group {group!r}; inspect field_groups()"
            )
        rows = [
            item
            for item in self._fields
            if (collection is None or item["collection"] == collection)
            and (group is None or item["group"] == group)
        ]
        return pd.DataFrame(
            deepcopy(rows),
            columns=[
                "name",
                "units",
                "description",
                "collection",
                "group",
                "notes",
                "source_url",
            ],
        )

    def field_groups_frame(
        self, flight: int | None, collection: str | None
    ) -> pd.DataFrame:
        fields = self.fields_frame(flight, collection, None)
        counts = (
            fields.groupby("group", sort=False)
            .agg(field_count=("name", "nunique"))
            .reset_index()
        )
        counts["description"] = counts["group"].map(GROUP_DESCRIPTIONS)
        return pd.DataFrame(counts, columns=["group", "description", "field_count"])

    def field_metadata(self, name: str, collection: str) -> dict[str, Any]:
        return deepcopy(self._by_field.get((collection, name), {}))

    def known_field(self, name: str) -> bool:
        return any(item["name"] == name for item in self._fields)

    def collection_fields(self, collection: str) -> tuple[str, ...]:
        return tuple(
            item["name"] for item in self._fields if item["collection"] == collection
        )

    def sensors_frame(self, flight: int | None, collection: str | None) -> pd.DataFrame:
        collection = self.resolve_collection(flight, collection)
        rows = [
            item
            for item in self._data["sensor_layout"]
            if collection is None or item["collection"] == collection
        ]
        return pd.DataFrame(
            deepcopy(rows),
            columns=[
                "collection",
                "sensor",
                "description",
                "x",
                "y",
                "z",
                "source_url",
            ],
        )

    def segments_frame(self, flights: int | Iterable[int] | None) -> pd.DataFrame:
        allowed = None if flights is None else set(flight_ids(flights))
        if allowed is not None:
            for flight in allowed:
                self.require_flight(flight)
        rows = [
            item
            for item in self._data["segments"]
            if allowed is None or item["flight"] in allowed
        ]
        return pd.DataFrame(
            deepcopy(rows),
            columns=[
                "flight",
                "segment",
                "line",
                "start_tt",
                "end_tt",
                "description",
                "is_holdout",
                "source_url",
            ],
        )
