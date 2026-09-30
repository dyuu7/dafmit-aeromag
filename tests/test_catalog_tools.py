from __future__ import annotations

import io
import zipfile

import pytest
from scripts.update_catalog import (
    _file_metadata,
    _read_zip,
    parse_field_notes,
    parse_fields,
    parse_flight_notes,
    parse_flight_readme,
    parse_sensor_layout,
)


def test_parse_fields_and_flight_readme() -> None:
    fields = parse_fields(
        """Field        Units  Description
====================================
line         -      line number
mag_1_uc     nT     corrected magnetic field
Notes follow
""",
        "2021",
    )
    assert [item["name"] for item in fields] == ["line", "mag_1_uc"]
    assert fields[1]["collection"] == "2021"

    date, segments = parse_flight_readme(
        """Flight 2005
21-Dec-2021 (doy = 355/365)
Start Time  End Time  Line Number    Description
  54616.00  55252.00      2004.00    Transit
  55252.00  56000.00      2004.01    HOLD-OUT TESTING DATA
""",
        2005,
    )
    assert date == "2021-12-21"
    assert segments[0]["is_holdout"] is False
    assert "released" not in segments[0]
    assert segments[1]["is_holdout"] is True


def test_parse_field_notes_sensor_layout_and_flight_notes() -> None:
    text = """Field        Units  Description
====================================
radar        m      radar altitude
ins_pitch    deg    aircraft pitch
ins_roll     deg    aircraft roll
Notes on specific flight data fields:

radar
- unavailable at some times

ins_pitch, ins_roll
- yaw then pitch then roll
  relative to the aircraft

Magnetometer/Fluxgate positions in reference to front seat rail [m]
  Sensor   Description                      X       Y       Z
-------------------------------------------------------------------
   Mag 1   Tail stinger                  -12.01    0       1.37
   Flux A  Near fuel tank                  -3.27   -0.60    0
For Flt1008 & Flt1009, orientation was modified
"""
    fields = parse_fields(text, "2020")
    notes = parse_field_notes(text, "2020", {item["name"] for item in fields})
    sensors = parse_sensor_layout(text, "2020")

    assert notes["radar"] == ["unavailable at some times"]
    assert notes["ins_pitch"] == ["yaw then pitch then roll relative to the aircraft"]
    assert notes["ins_roll"] == notes["ins_pitch"]
    assert sensors[0]["sensor"] == "Mag 1"
    assert sensors[0]["x"] == -12.01
    assert sensors[1]["sensor"] == "Flux A"

    assert parse_flight_notes("- calibration\n- repeat lines\nStart Time") == [
        "calibration",
        "repeat lines",
    ]


def test_table_parsers_reject_unrecognized_rows_and_duplicates() -> None:
    with pytest.raises(ValueError, match=r"sgl_2021_fields_readme.txt:3: invalid"):
        parse_fields(
            "Field Units Description\n"
            "mag_1_uc  nT  magnetic field\n"
            "ins_lat m latitude\n",
            "2021",
        )
    with pytest.raises(ValueError, match="duplicate field 'mag_1_uc'"):
        parse_fields(
            "Field Units Description\nmag_1_uc  nT  field\nmag_1_uc  nT  field\n",
            "2021",
        )
    with pytest.raises(ValueError, match=r"sgl_2020_fields_readme.txt:4: invalid"):
        parse_sensor_layout(
            "Magnetometer/Fluxgate positions\n"
            "Sensor Description X Y Z\n"
            "Mag 1 Tail stinger -12 0 1\n"
            "Mag 2 missing-coordinate -3 0\n",
            "2020",
        )
    with pytest.raises(ValueError, match=r"Flt2005_readme.txt:4: invalid"):
        parse_flight_readme(
            "Flight 2005\n21-Dec-2021\n"
            "Start Time End Time Line Number Description\n"
            "malformed segment row\n",
            2005,
        )


def test_field_notes_reject_unknown_headings_and_orphan_bullets() -> None:
    with pytest.raises(ValueError, match="missing field notes section"):
        parse_field_notes("Field Units Description", "2020", {"ins_pitch"})
    with pytest.raises(ValueError, match=r"sgl_2020_fields_readme.txt:5: invalid"):
        parse_field_notes(
            "Notes on specific flight data fields:\n"
            "ins_pitch\n- known note\n\nunknown_field\n- misplaced note\n",
            "2020",
            {"ins_pitch"},
        )
    with pytest.raises(ValueError, match=r"sgl_2020_fields_readme.txt:2: invalid"):
        parse_field_notes(
            "Notes on specific flight data fields:\n- no field heading\n",
            "2020",
            {"ins_pitch"},
        )


def test_readme_archive_rejects_duplicate_names_and_invalid_text() -> None:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("a/Flt2005_readme.txt", "first")
        stream.writestr("b/flt2005_readme.txt", "second")
    with pytest.raises(ValueError, match="duplicate readme archive filename"):
        _read_zip(archive.getvalue())

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("Flt2005_readme.txt", b"date\n\xff")
    with pytest.raises(ValueError, match=r"Flt2005_readme.txt:2: invalid UTF-8"):
        _read_zip(archive.getvalue())


def test_zenodo_record_rejects_duplicate_flights() -> None:
    item = {
        "key": "Flt2005_train.h5",
        "checksum": "md5:" + "0" * 32,
        "links": {"content": "https://example.invalid/2005.h5"},
        "size": 1,
    }
    with pytest.raises(ValueError, match="duplicate flight 2005"):
        _file_metadata({"files": [item, item]})


def test_catalog_generation_from_release_archives(monkeypatch):
    import json

    from scripts import update_catalog as updater

    field_text = (
        "Field        Units  Description\nmag_1_uc     nT     magnetic measurement\n"
        "Notes on specific flight data fields:\n"
        "Magnetometer/Fluxgate positions\n"
        "Sensor Description X Y Z\n"
        "Mag 1 Tail stinger -12 0 1\n"
    )
    readmes = {
        "sgl_2020_fields_readme.txt": field_text,
        "sgl_2021_fields_readme.txt": field_text,
        "Flt1004_readme.txt": (
            "Flight 1004\n30-Jun-2020\n"
            "Start Time  End Time  Line Number    Description\n"
            "  1.0  2.0  1004.01  Transit\n"
            "  2.0  3.0  4014.00  HOLD-OUT TESTING DATA\n"
        ),
        "Flt2005_readme.txt": (
            "Flight 2005\n21-Dec-2021\n"
            "Start Time  End Time  Line Number    Description\n"
            "  4.0  5.0  2004.00  Transit\n"
            "  5.0  6.0  2004.01  HOLD-OUT TESTING DATA\n"
        ),
    }
    archives = {}
    for collection, flight in [("2020", 1004), ("2021", 2005)]:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            for name in [
                f"sgl_{collection}_fields_readme.txt",
                f"Flt{flight}_readme.txt",
            ]:
                archive.writestr(name, readmes[name])
        archives[f"https://example.invalid/{collection}.zip"] = stream.getvalue()
    record = {
        "id": 12723700,
        "metadata": {},
        "files": [
            {
                "key": f"Flt{flight}_train.h5",
                "size": 1,
                "checksum": "md5:" + "0" * 32,
                "links": {"content": f"https://example.invalid/{flight}.h5"},
            }
            for flight in (1004, 2005)
        ]
        + [
            {
                "key": f"{year}_Flight_Readme_Files.zip",
                "links": {"content": f"https://example.invalid/{year}.zip"},
            }
            for year in ("2020", "2021")
        ],
    }
    responses = {
        "https://zenodo.org/api/records/12723700": json.dumps(record).encode(),
        **archives,
    }
    monkeypatch.setattr(updater, "_get_bytes", lambda url: responses[url])
    generated = updater.build_catalog()
    assert generated["release"] == "v3"
    assert generated["record_id"] == 12723700
    assert generated["generated_from"] == "https://zenodo.org/api/records/12723700"
    assert [f["flight"] for f in generated["flights"]] == [1004, 2005]
    assert [f["date"] for f in generated["flights"]] == ["2020-06-30", "2021-12-21"]
    assert [f["collection"] for f in generated["fields"]] == ["2020", "2021"]
    assert [s["is_holdout"] for s in generated["segments"]] == [
        False,
        True,
        False,
        True,
    ]
    assert all("source_url" in s for s in generated["segments"])
    assert all("has_holdout" not in f for f in generated["flights"])
