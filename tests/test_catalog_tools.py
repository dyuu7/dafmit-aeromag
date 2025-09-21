from __future__ import annotations

from scripts.update_catalog import (
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
    assert segments[0]["released"] is True
    assert segments[1]["split"] == "holdout"


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
    assert notes["ins_pitch"] == ["yaw then pitch then roll"]
    assert sensors[0]["sensor"] == "Mag 1"
    assert sensors[0]["x"] == -12.01
    assert sensors[1]["sensor"] == "Flux A"

    assert parse_flight_notes("- calibration\n- repeat lines\nStart Time") == [
        "calibration",
        "repeat lines",
    ]
