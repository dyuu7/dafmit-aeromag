#!/usr/bin/env python3
"""Generate the checked-in catalog from a Zenodo record.

The script deliberately downloads only Zenodo metadata and the small upstream
readme archives. HDF5 payloads are never needed to rebuild the catalog.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_OUTPUT = _ROOT / "src" / "dafmit_aeromag" / "catalog" / "v3.json"
_ZENODO_API = "https://zenodo.org/api/records"
_UPSTREAM_REPOSITORY = "https://github.com/MIT-AI-Accelerator/MagNav.jl"
# This revision contains the readmes used for the v3 metadata interpretation.
_UPSTREAM_REVISION = "b79a9ceed6009878f47c72938718f96ce067d803"
_UPSTREAM_READMES = f"{_UPSTREAM_REPOSITORY}/blob/{_UPSTREAM_REVISION}/readmes"
_UPSTREAM_READMES_TREE = f"{_UPSTREAM_REPOSITORY}/tree/{_UPSTREAM_REVISION}/readmes"
_UPSTREAM_RAW_READMES = (
    "https://raw.githubusercontent.com/MIT-AI-Accelerator/MagNav.jl/"
    f"{_UPSTREAM_REVISION}/readmes"
)
_LINE_RE = re.compile(
    r"^\s*(?P<start>[0-9]+(?:\.[0-9]+)?)\s+"
    r"(?P<stop>[0-9]+(?:\.[0-9]+)?)\s+"
    r"(?P<line>[0-9]+(?:\.[0-9]+)?)\s+(?P<description>.+?)\s*$"
)
_DATE_RE = re.compile(r"(?P<date>\d{2}-[A-Za-z]{3}-\d{4})")


def _field_group(name: str) -> str:
    """Assign a stable convenience group without renaming source fields."""

    if name in {"line", "flight", "year", "doy", "tt"}:
        return "identity"
    if name == "diurnal" or name.startswith("mag_"):
        return "scalar_magnetometer"
    if name.startswith("flux_"):
        return "fluxgate"
    if name.startswith("ins_"):
        return "ins"
    if name.startswith("cur_"):
        return "current"
    if name.startswith("vol_"):
        return "voltage"
    if name.startswith("ogs_"):
        return "reference"
    if name in {
        "pitch_rate",
        "roll_rate",
        "yaw_rate",
        "lgtl_acc",
        "ltrl_acc",
        "nrml_acc",
        "tas",
        "pitot_p",
        "static_p",
        "total_p",
    }:
        return "avionics"
    return "navigation"


def _get_json(url: str) -> dict[str, Any]:
    return json.loads(_get_bytes(url))


def _get_bytes(url: str, *, timeout: int = 120) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "dafmit-aeromag"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (TimeoutError, urllib.error.HTTPError, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(2**attempt)


def _get_text(url: str) -> str:
    return _get_bytes(url).decode("utf-8", errors="replace")


def _canonical_line(value: str) -> str:
    return f"{float(value):.2f}"


def _read_zip(payload: bytes) -> dict[str, str]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        result: dict[str, str] = {}
        for name in archive.namelist():
            if name.endswith("/") or "__MACOSX" in name:
                continue
            short_name = Path(name).name
            result[short_name] = archive.read(name).decode("utf-8", errors="replace")
    return result


def parse_fields(text: str, collection: str) -> list[dict[str, str]]:
    """Parse the compact field table shipped with a release."""

    fields: list[dict[str, str]] = []
    seen: set[str] = set()
    in_table = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.lower().startswith("field") and "description" in line.lower():
            in_table = True
            continue
        if not in_table or not line or set(line) <= {"=", "-", " "}:
            continue
        if line.lower().startswith(("notes", "references", "the following")):
            break
        match = re.match(
            r"^\s*([A-Za-z][A-Za-z0-9_]*)\s+(\S+)\s{2,}(.+?)\s*$",
            raw_line,
        )
        if match is None:
            continue
        name, units, description = match.groups()
        if name in seen:
            continue
        seen.add(name)
        fields.append(
            {
                "name": name,
                "units": units,
                "description": description,
                "collection": collection,
                "group": _field_group(name),
            }
        )
    if not fields:
        raise ValueError(f"could not parse any fields for collection {collection}")
    return fields


def parse_field_notes(
    text: str,
    collection: str,
    field_names: set[str],
) -> dict[str, list[str]]:
    """Parse field-specific notes from an upstream field readme."""

    marker = "Notes on specific flight data fields:"
    if marker not in text:
        return {}
    section = text.split(marker, 1)[1].split(
        "Magnetometer/Fluxgate positions", 1
    )[0]
    notes: dict[str, list[str]] = {}
    current: tuple[str, ...] = ()
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line or set(line) <= {"=", "-", " "}:
            continue
        if line.startswith("-"):
            if current:
                value = line.lstrip("- ").strip()
                for name in current:
                    notes.setdefault(name, []).append(value)
            continue
        names = tuple(
            part.strip()
            for part in re.split(r"\s*(?:,|&)\s*", line)
            if part.strip()
        )
        if names and all(name in field_names for name in names):
            current = names
    return notes


def parse_sensor_layout(text: str, collection: str) -> list[dict[str, Any]]:
    """Parse the primary magnetometer/fluxgate layout table."""

    marker = "Magnetometer/Fluxgate positions"
    if marker not in text:
        return []
    section = text.split(marker, 1)[1].split("For Flt1008", 1)[0]
    number = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"
    pattern = re.compile(
        rf"^(?P<sensor>Mag \d|Flux [A-D])\s+"
        rf"(?P<description>.+?)\s+"
        rf"(?P<x>{number})\s+(?P<y>{number})\s+(?P<z>{number})\s*$"
    )
    rows: list[dict[str, Any]] = []
    for raw_line in section.splitlines():
        match = pattern.match(raw_line.strip())
        if match is None:
            continue
        rows.append(
            {
                "collection": collection,
                "sensor": match.group("sensor"),
                "description": match.group("description").strip(),
                "x": float(match.group("x")),
                "y": float(match.group("y")),
                "z": float(match.group("z")),
            }
        )
    return rows


def parse_flight_notes(text: str) -> list[str]:
    """Parse bullet notes that precede a flight's segment table."""

    if "Start Time" not in text:
        return []
    preamble = text.split("Start Time", 1)[0]
    notes: list[str] = []
    for raw_line in preamble.splitlines():
        line = raw_line.strip()
        if line.startswith("-"):
            notes.append(line.lstrip("- ").strip())
    return notes


def parse_flight_readme(text: str, flight: int) -> tuple[str, list[dict[str, Any]]]:
    """Parse a flight readme into its date and segment rows."""

    date_match = _DATE_RE.search(text)
    if date_match is None:
        raise ValueError(f"could not find collection date for flight {flight}")
    collection_date = datetime.strptime(date_match.group("date"), "%d-%b-%Y").date()
    segments: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        match = _LINE_RE.match(raw_line)
        if match is None:
            continue
        start, stop, line, description = match.groups()
        lowered = description.lower()
        split = "holdout" if "hold-out" in lowered or "holdout" in lowered else "train"
        segments.append(
            {
                "flight": flight,
                "segment": len(segments) + 1,
                "line": _canonical_line(line),
                "start_tt": float(start),
                "end_tt": float(stop),
                "description": description.strip(),
                "split": split,
                "released": split == "train",
            }
        )
    if not segments:
        raise ValueError(f"could not parse segments for flight {flight}")
    return collection_date.isoformat(), segments


def _file_metadata(record: dict[str, Any]) -> dict[int, dict[str, Any]]:
    files: dict[int, dict[str, Any]] = {}
    for item in record.get("files", []):
        key = item.get("key", "")
        match = re.fullmatch(r"Flt(?P<flight>\d+)_train\.h5", Path(key).name)
        if match is None:
            continue
        flight = int(match.group("flight"))
        checksum = item.get("checksum", "")
        if not checksum.startswith("md5:"):
            raise ValueError(f"unexpected checksum for {key}: {checksum}")
        url = item.get("links", {}).get("content") or item.get("links", {}).get("self")
        if not url:
            raise ValueError(f"missing direct download URL for {key}")
        files[flight] = {
            "file": key,
            "url": url,
            "size_bytes": int(item["size"]),
            "checksum": checksum.removeprefix("md5:"),
        }
    if not files:
        raise ValueError("Zenodo record did not contain Flt*_train.h5 files")
    return files


def _find_readme_zip(record: dict[str, Any], collection: str) -> str:
    target = f"{collection}_Flight_"
    for item in record.get("files", []):
        key = Path(item.get("key", "")).name
        if key.startswith(target) and key.endswith("Readme_Files.zip"):
            url = item.get("links", {}).get("content") or item.get("links", {}).get(
                "self"
            )
            if url:
                return url
            raise ValueError(f"missing direct download URL for {key}")
    raise ValueError(f"could not find {collection} readme archive")


def build_catalog(record_id: int) -> dict[str, Any]:
    record = _get_json(f"{_ZENODO_API}/{record_id}")
    metadata = record.get("metadata", {})
    files = _file_metadata(record)
    archives: dict[str, dict[str, str]] = {}
    readmes: dict[str, str] = {}
    field_notes: dict[tuple[str, str], list[str]] = {}
    sensor_layout: list[dict[str, Any]] = []
    for collection in ("2020", "2021"):
        archive = _read_zip(_get_bytes(_find_readme_zip(record, collection)))
        archives[collection] = archive
        field_name = f"sgl_{collection}_fields_readme.txt"
        field_text = next(
            (
                text
                for name, text in archive.items()
                if name.lower() == field_name.lower()
            ),
            None,
        )
        if field_text is None:
            raise ValueError(f"missing {field_name} in readme archive")
        readmes[collection] = field_text
        parsed_fields = parse_fields(field_text, collection)
        names = {item["name"] for item in parsed_fields}
        field_notes.update(
            {
                (collection, name): values
                for name, values in parse_field_notes(
                    field_text, collection, names
                ).items()
            }
        )
        sensor_source_url = f"{_UPSTREAM_READMES}/{field_name}"
        sensor_layout.extend(
            {
                **row,
                "source_url": sensor_source_url,
            }
            for row in parse_sensor_layout(field_text, collection)
        )

    flights: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    for flight in sorted(files):
        collection = "2020" if flight < 2000 else "2021"
        archive = archives[collection]
        stem = f"Flt{flight}_readme.txt"
        text = next(
            (
                value
                for name, value in archive.items()
                if Path(name).name.lower() == stem.lower()
            ),
            None,
        )
        if text is None:
            raise ValueError(f"missing {stem} in {collection} readme archive")
        date, flight_segments = parse_flight_readme(text, flight)
        flight_notes = parse_flight_notes(text)
        flights.append(
            {
                "flight": flight,
                "collection": collection,
                "date": date,
                "file": files[flight]["file"],
                "url": files[flight]["url"],
                "size_bytes": files[flight]["size_bytes"],
                "checksum": files[flight]["checksum"],
                "dt": 0.1,
                "has_holdout": any(
                    row["split"] == "holdout" for row in flight_segments
                ),
                "notes": flight_notes,
                "source_url": f"{_UPSTREAM_READMES}/Flt{flight}_readme.txt",
            }
        )
        segments.extend(flight_segments)

    return {
        "release": "v3",
        "record_id": int(record["id"]),
        "version": metadata.get("version", "3"),
        "doi": metadata.get("doi", "10.5281/zenodo.12723700"),
        "concept_doi": metadata.get("conceptdoi", "10.5281/zenodo.4271803"),
        "title": metadata.get("title", "DAF-MIT AIA Open Flight Data"),
        "source_url": f"https://zenodo.org/records/{record['id']}",
        "generated_from": f"{_ZENODO_API}/{record['id']}",
        "sources": {
            "data_release": f"https://zenodo.org/records/{record['id']}",
            "release_metadata": f"https://zenodo.org/records/{record['id']}",
            "upstream_repository": _UPSTREAM_REPOSITORY,
            "upstream_revision": _UPSTREAM_REVISION,
            "mag_nav_readmes": _UPSTREAM_READMES_TREE,
            "fields_2020": f"{_UPSTREAM_READMES}/sgl_2020_fields_readme.txt",
            "fields_2021": f"{_UPSTREAM_READMES}/sgl_2021_fields_readme.txt",
            "datasheet_2020": f"{_UPSTREAM_READMES}/datasheet_sgl_2020_train.pdf",
            "datasheet_2021": f"{_UPSTREAM_READMES}/datasheet_sgl_2021_train.pdf",
        },
        "flights": flights,
        "fields": [
            {
                **field,
                "notes": field_notes.get(
                    (field["collection"], field["name"]), []
                ),
                "source_url": (
                    f"{_UPSTREAM_READMES}/sgl_"
                    f"{field['collection']}_fields_readme.txt"
                ),
            }
            for collection in ("2020", "2021")
            for field in parse_fields(readmes[collection], collection)
        ],
        "sensor_layout": sensor_layout,
        "segments": segments,
    }


def build_catalog_from_existing(base_path: Path) -> dict[str, Any]:
    """Refresh metadata from upstream readmes using an existing file manifest.

    This path is useful when the Zenodo API is temporarily unavailable. The
    checked-in catalog remains the source for file URLs, sizes, and checksums;
    field definitions and flight notes still come from upstream readmes.
    """

    base = json.loads(base_path.read_text(encoding="utf-8"))
    readmes = {
        collection: _get_text(
            f"{_UPSTREAM_RAW_READMES}/sgl_{collection}_fields_readme.txt"
        )
        for collection in ("2020", "2021")
    }
    parsed_fields = {
        collection: parse_fields(text, collection)
        for collection, text in readmes.items()
    }
    field_notes = {
        (collection, name): values
        for collection, text in readmes.items()
        for name, values in parse_field_notes(
            text,
            collection,
            {item["name"] for item in parsed_fields[collection]},
        ).items()
    }
    sensor_layout = [
        {
            **row,
            "source_url": f"{_UPSTREAM_READMES}/sgl_{collection}_fields_readme.txt",
        }
        for collection, text in readmes.items()
        for row in parse_sensor_layout(text, collection)
    ]

    flights: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    for item in base["flights"]:
        flight = int(item["flight"])
        text = _get_text(f"{_UPSTREAM_RAW_READMES}/Flt{flight}_readme.txt")
        date, flight_segments = parse_flight_readme(text, flight)
        flights.append(
            {
                **item,
                "date": date,
                "has_holdout": any(
                    row["split"] == "holdout" for row in flight_segments
                ),
                "notes": parse_flight_notes(text),
                "source_url": f"{_UPSTREAM_READMES}/Flt{flight}_readme.txt",
            }
        )
        segments.extend(flight_segments)

    return {
        **base,
        "sources": {
            "data_release": base["source_url"],
            "release_metadata": base["source_url"],
            "upstream_repository": _UPSTREAM_REPOSITORY,
            "upstream_revision": _UPSTREAM_REVISION,
            "mag_nav_readmes": _UPSTREAM_READMES_TREE,
            "fields_2020": f"{_UPSTREAM_READMES}/sgl_2020_fields_readme.txt",
            "fields_2021": f"{_UPSTREAM_READMES}/sgl_2021_fields_readme.txt",
            "datasheet_2020": f"{_UPSTREAM_READMES}/datasheet_sgl_2020_train.pdf",
            "datasheet_2021": f"{_UPSTREAM_READMES}/datasheet_sgl_2021_train.pdf",
        },
        "flights": flights,
        "fields": [
            {
                **field,
                "notes": field_notes.get((field["collection"], field["name"]), []),
                "source_url": (
                    f"{_UPSTREAM_READMES}/sgl_{field['collection']}"
                    "_fields_readme.txt"
                ),
            }
            for collection in ("2020", "2021")
            for field in parsed_fields[collection]
        ],
        "sensor_layout": sensor_layout,
        "segments": segments,
    }


def _serialise(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=int, default=12723700)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    parser.add_argument(
        "--base-catalog",
        type=Path,
        help="refresh metadata from upstream readmes using an existing catalog",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="check whether the checked-in catalog is current without writing it",
    )
    args = parser.parse_args()
    source = (
        build_catalog_from_existing(args.base_catalog)
        if args.base_catalog is not None
        else build_catalog(args.record)
    )
    generated = _serialise(source)
    if args.check:
        if (
            not args.output.exists()
            or args.output.read_text(encoding="utf-8") != generated
        ):
            print(f"catalog is stale: {args.output}", file=sys.stderr)
            return 1
        print(f"catalog is current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generated, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
