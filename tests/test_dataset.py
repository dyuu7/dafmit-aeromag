from __future__ import annotations

import pandas as pd
import pytest

from dafmit_aeromag import (
    InvalidSelectionError,
    MissingFieldError,
    NoDataError,
    Selection,
    UnknownFieldError,
)


def test_catalog_is_versioned_and_keeps_duplicate_segments(synthetic_dataset) -> None:
    flights = synthetic_dataset.flights()
    assert len(flights) == 16
    assert set(flights["collection"]) == {"2020", "2021"}
    assert synthetic_dataset.flights("2021")["flight"].tolist() == [
        2001,
        2002,
        2004,
        2005,
        2006,
        2007,
        2008,
        2015,
        2016,
        2017,
    ]

    segments = synthetic_dataset.segments(1002)
    duplicate = segments.loc[segments["line"] == "1002.14"]
    assert len(duplicate) == 2
    assert set(duplicate["split"]) == {"train", "holdout"}

    fields = synthetic_dataset.fields(2005)
    assert fields.loc[fields["name"] == "flux_a_x", "available"].any()
    assert len(synthetic_dataset.fields(collection="2021")) == 61
    assert "source_url" in fields.columns
    assert "utm_x" in synthetic_dataset.field_names("navigation", flight=2005)
    assert "drape" not in synthetic_dataset.field_names("navigation", flight=2005)
    assert "flux_a_x" in synthetic_dataset.field_names("fluxgate", flight=2005)
    assert synthetic_dataset.sensors("2020").shape[0] == 9
    sources = synthetic_dataset.catalog.metadata["sources"]
    assert sources["upstream_revision"] == ("b79a9ceed6009878f47c72938718f96ce067d803")
    assert "master" not in sources["mag_nav_readmes"]


def test_normalized_read_derives_2020_identity(synthetic_dataset) -> None:
    frame = synthetic_dataset.read(
        Selection(1002, lines="1002.01"),
        columns=["mag_1_uc", "ins_lat"],
    )

    assert list(frame.columns[:6]) == ["flight", "line", "year", "doy", "tt", "time"]
    assert frame["flight"].tolist() == [1002, 1002]
    assert frame["line"].tolist() == ["1002.01", "1002.01"]
    assert frame["year"].tolist() == [2020, 2020]
    assert frame["doy"].tolist() == [172, 172]
    assert frame["time"].iloc[0] == pd.Timestamp("2020-06-20 12:31:40", tz="UTC")


def test_line_selection_is_scoped_to_file_flight(synthetic_dataset) -> None:
    frame = synthetic_dataset.read(
        Selection(2005, lines="2004.00"),
        columns=["mag_1_uc"],
    )

    assert len(frame) == 2
    assert frame["flight"].unique().tolist() == [2005]
    assert frame["mag_1_uc"].tolist() == [10.0, 11.0]


def test_multi_selection_order_and_fill(synthetic_dataset) -> None:
    frame = synthetic_dataset.read(
        [Selection(1002, lines="1002.02"), Selection(2005, lines="2005.20")],
        columns=["mag_1_uc", "flux_a_x"],
        missing="fill",
    )

    assert frame["flight"].tolist() == [1002, 1002, 2005]
    assert frame["flux_a_x"].iloc[:2].isna().all()
    assert frame["flux_a_x"].iloc[2] == 22.0


def test_missing_physical_field_raises_by_default(synthetic_dataset) -> None:
    with pytest.raises(MissingFieldError, match="flux_a_x"):
        synthetic_dataset.read(
            Selection(1002, lines="1002.01"),
            columns=["flux_a_x"],
        )


def test_raw_mode_has_no_derived_or_scalar_fields(synthetic_dataset) -> None:
    frame = synthetic_dataset.read(
        Selection(1002, lines="1002.01"),
        columns=["tt", "mag_1_uc"],
        raw=True,
    )
    assert list(frame.columns) == ["tt", "mag_1_uc"]
    assert len(frame) == 2

    all_raw = synthetic_dataset.read(Selection(1002), columns="all", raw=True)
    assert "N" not in all_raw
    assert "dt" not in all_raw
    assert "info" not in all_raw
    assert "mag_1_uc" in all_raw


def test_time_bounds_are_left_closed_and_right_open(synthetic_dataset) -> None:
    frame = synthetic_dataset.read(
        Selection(1002, time=slice("2020-06-20 12:31:40.1", "2020-06-20 12:31:40.2")),
        columns=["mag_1_uc"],
    )
    assert frame["tt"].tolist() == [45100.1]


def test_unreleased_holdout_intervals_are_not_read(synthetic_dataset) -> None:
    frame = synthetic_dataset.read(Selection.all(1002), columns=["mag_1_uc"])

    assert len(frame) == 4
    assert "320.00" not in frame["line"].tolist()


def test_read_split_selects_train_holdout_or_all(synthetic_dataset) -> None:
    selection = Selection.all(1002)
    train = synthetic_dataset.read(selection, columns=["mag_1_uc"], split="train")
    holdout = synthetic_dataset.read(
        selection,
        columns=["mag_1_uc"],
        split="holdout",
    )
    all_samples = synthetic_dataset.read(
        selection,
        columns=["mag_1_uc"],
        split="all",
    )

    assert len(train) == 4
    assert len(holdout) == 1
    assert holdout["line"].tolist() == ["320.00"]
    assert len(all_samples) == 5
    assert train.attrs["split"] == "train"
    assert holdout.attrs["split"] == "holdout"
    assert all_samples.attrs["split"] == "all"


def test_read_rejects_unknown_split(synthetic_dataset) -> None:
    with pytest.raises(ValueError, match="split must be"):
        synthetic_dataset.read(
            Selection.all(1002),
            columns=["mag_1_uc"],
            split="validation",
        )


def test_xarray_conversion_uses_identity_coordinates(synthetic_dataset) -> None:
    frame = synthetic_dataset.read(Selection(1002), columns=["mag_1_uc"])
    array = synthetic_dataset.to_xarray(frame)

    assert array.sizes["sample"] == 4
    assert "time" in array.coords
    assert "flight" in array.coords
    assert "mag_1_uc" in array.data_vars
    assert array.attrs["release"] == "v3"


def test_empty_selection_and_unknown_field_are_actionable(synthetic_dataset) -> None:
    with pytest.raises(NoDataError):
        synthetic_dataset.read(Selection(1002, lines="9999.00"), columns=["mag_1_uc"])
    with pytest.raises(UnknownFieldError):
        synthetic_dataset.read(Selection(1002), columns=["not_a_field"])
    with pytest.raises(InvalidSelectionError):
        synthetic_dataset.read([], columns=["mag_1_uc"])


def test_offline_fetch_reports_missing_files(tmp_path) -> None:
    from dafmit_aeromag import Dataset, DataUnavailableError

    with pytest.raises(DataUnavailableError, match="offline mode"):
        Dataset(data_dir=tmp_path, offline=True).fetch(2005)
