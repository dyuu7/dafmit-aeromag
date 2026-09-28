from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dafmit_aeromag import (
    DataIntegrityError,
    Dataset,
    DataUnavailableError,
    InvalidArgumentError,
    MissingFieldError,
    Selection,
    UnknownFieldError,
    UnknownFlightError,
)


def test_catalog_queries_are_offline_and_scope_to_collection(tmp_path):
    data = Dataset(data_dir=tmp_path / "absent", offline=True)
    assert len(data.flights()) == 16
    assert len(data.fields(flight=2005)) == 61
    assert data.fields(flight=2005).name.is_unique
    assert set(data.fields(flight=2005).collection) == {"2021"}
    assert "available" not in data.fields(flight=2005)
    assert "has_holdout" not in data.flights()
    assert len(data.segments()) == 175
    assert data.segments().is_holdout.sum() == 19
    duplicates = data.segments(1002).query("line == '1002.14'")
    assert len(duplicates) == 2
    assert set(duplicates.is_holdout) == {True, False}
    assert "released" not in duplicates
    assert "split" not in duplicates
    assert data.segments([1002, 2005]).source_url.str.contains("b79a9ceed600").all()
    assert len(data.sensors(flight=2005)) == len(data.sensors(collection="2021"))
    assert not data.data_dir.exists()


def test_field_names_and_groups_are_real_summaries(synthetic_dataset):
    data = synthetic_dataset
    names = data.field_names(group="scalar_magnetometer")
    assert len(names) == len(set(names))
    assert names == tuple(dict.fromkeys(data.fields(group="scalar_magnetometer").name))
    groups = data.field_groups(flight=2005)
    assert groups.group.is_unique
    assert groups.field_count.sum() == 61
    assert "utm_x" in data.field_names(flight=2005, group="navigation")


def test_catalog_results_do_not_expose_mutable_state(synthetic_dataset):
    data = synthetic_dataset
    other = Dataset(offline=True)
    before = data.metadata
    data.metadata["sources"]["upstream_revision"] = "modified"
    flights = data.flights()
    flights.loc[0, "date"] = "1999-01-01"
    flights.loc[0, "notes"].append("modified")
    fields = data.fields()
    fields.loc[0, "notes"].append("modified")
    assert data.metadata == before == other.metadata
    assert "modified" not in data.flights().loc[0, "notes"]
    assert "modified" not in other.flights().loc[0, "notes"]
    assert "modified" not in data.fields().loc[0, "notes"]
    assert data.flights().loc[0, "date"] != "1999-01-01"
    with pytest.raises(AttributeError):
        data.release = "other"


@pytest.mark.parametrize("method", ["fields", "field_names", "field_groups", "sensors"])
def test_conflicting_catalog_scopes_raise(synthetic_dataset, method):
    with pytest.raises(InvalidArgumentError, match="either flight or collection"):
        getattr(synthetic_dataset, method)(flight=2005, collection="2021")


def test_normalized_identity_and_boundary_sample(synthetic_dataset):
    data = synthetic_dataset
    frame = data.read(Selection(1002, lines="1002.01"), columns=["mag_1_uc", "ins_lat"])
    assert frame.flight.tolist() == [1002, 1002]
    assert frame.year.tolist() == [2020, 2020]
    assert frame.doy.tolist() == [172, 172]
    assert frame.time.iloc[0] == pd.Timestamp("2020-06-20 12:31:40", tz="UTC")
    all_rows = data.read(Selection(2005, lines="2004.00"), columns="mag_1_uc")
    assert all_rows.tt.tolist() == [54616.0, 54616.1, 55252.0]
    limited = data.read(Selection(2005, tt=slice(54616, 55252)), columns="mag_1_uc")
    assert limited.tt.tolist() == [54616.0, 54616.1]


def test_time_filter_is_half_open_and_normalized(synthetic_dataset):
    frame = synthetic_dataset.read(
        Selection(
            1002, time=slice("2020-06-20T20:31:40.1+08:00", "2020-06-20T12:31:40.2Z")
        ),
        columns="mag_1_uc",
    )
    assert frame.tt.tolist() == [45100.1]
    assert frame.attrs["selections"][0]["time"][0] == "2020-06-20T12:31:40.100000+00:00"


def test_batch_generator_fill_and_units(synthetic_dataset):
    query = (s for s in [Selection(1002, lines="1002.02"), Selection(2005)])
    frame = synthetic_dataset.read(
        query, columns=np.array(["mag_1_uc", "flux_a_x"]), missing="fill"
    )
    assert frame.flight.tolist() == [1002, 1002, 2005, 2005, 2005]
    assert frame.flux_a_x.iloc[:2].isna().all()
    assert frame.flux_a_x.iloc[2:].tolist() == [20.0, 21.0, 22.0]
    assert frame.attrs["units"]["mag_1_uc"] == "nT"


def test_missing_and_unknown_fields_are_distinct(synthetic_dataset):
    with pytest.raises(MissingFieldError, match="flux_a_x"):
        synthetic_dataset.read(Selection(1002), columns="flux_a_x")
    with pytest.raises(UnknownFieldError, match="no_such_field"):
        synthetic_dataset.read(Selection(1002), columns="no_such_field", missing="fill")


def test_raw_and_identity_only(synthetic_dataset):
    data = synthetic_dataset
    raw = data.read(Selection(1002), columns=["line", "mag_1_uc"], raw=True)
    assert raw.columns.tolist() == ["line", "mag_1_uc"]
    assert raw.line.dtype == np.dtype("float64")
    assert data.read(Selection(1002), columns=[]).shape == (5, 6)
    all_raw = data.read(Selection(1002), columns="all", raw=True)
    assert not {"time", "year", "N", "dt", "info"} & set(all_raw)
    filled = data.read(Selection(1002), columns="year", raw=True, missing="fill")
    assert filled.year.isna().all()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"columns": [], "raw": True},
        {"columns": "time", "raw": True},
        {"columns": "N", "missing": "fill"},
        {"columns": "dt"},
        {"columns": "info"},
        {"columns": {"mag_1_uc"}},
        {"columns": {"mag_1_uc": 1}},
        {"columns": "mag_1_uc", "empty": "skip"},
        {"columns": "mag_1_uc", "missing": "ignore"},
        {"columns": "mag_1_uc", "raw": "yes"},
    ],
)
def test_bad_read_arguments_fail_before_file_access(tmp_path, kwargs):
    data = Dataset(data_dir=tmp_path, offline=True)
    with pytest.raises(InvalidArgumentError):
        data.read(Selection(2005), **kwargs)


def test_inspection_reports_actual_fields(synthetic_dataset):
    data = synthetic_dataset
    info = data.inspect(2005)
    assert info.sample_count == 3
    assert info.dt == 0.1
    assert info.tt_range == (54616.0, 55252.0)
    assert info.fields.name.is_unique
    assert not {"time", "N", "dt", "info"} & set(info.fields.name)
    frame = data.read(Selection(2005), columns=info.fields.name, raw=True)
    assert set(frame) == set(info.fields.name)
    info.fields.loc[0, "name"] = "modified"
    assert "modified" not in set(data.inspect(2005).fields.name)
    missing = set(data.fields(flight=1002).name) - set(data.inspect(1002).fields.name)
    assert {"year", "doy", "mag_6_uc"} <= missing


def test_undocumented_sample_fields_are_readable(dataset_factory):
    data = dataset_factory(
        lambda files: files[1002].update(custom_signal=np.arange(5, dtype=np.int16))
    )
    info = data.inspect(1002)
    assert info.fields.set_index("name").loc["custom_signal", "units"] == ""
    explicit = data.read(Selection(1002), columns="custom_signal", raw=True)
    all_fields = data.read(Selection(1002), columns="all", raw=True)
    pd.testing.assert_series_equal(explicit.custom_signal, all_fields.custom_signal)
    with pytest.raises(MissingFieldError, match="custom_signal"):
        data.read([Selection(1002), Selection(2005)], columns="custom_signal")
    filled = data.read(
        [Selection(1002), Selection(2005)], columns="custom_signal", missing="fill"
    )
    assert filled.custom_signal.iloc[5:].isna().all()


def test_all_columns_union_missing_and_empty_schema(synthetic_dataset):
    data = synthetic_dataset
    with pytest.raises(MissingFieldError):
        data.read([Selection(1002), Selection(2005)], columns="all")
    frame = data.read([Selection(1002), Selection(2005)], columns="all", missing="fill")
    assert frame.shape[0] == 8
    assert {"ins_lat", "flux_a_x"} <= set(frame)
    assert frame.ins_lat.iloc[5:].isna().all()
    empty = data.read(
        [Selection(1002, lines="9999"), Selection(2005, lines="9999")],
        columns="all",
        missing="fill",
        empty="allow",
    )
    assert empty.columns.tolist() == frame.columns.tolist()
    assert empty.dtypes.to_dict() == frame.dtypes.to_dict()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mag_1_uc", np.array([1.0, 2.0])),
        ("mag_1_uc", np.ones((3, 1))),
        ("flight", np.array([2005.0, 2005.5, 2005.0])),
        ("flight", np.array([2005.0, 2017.0, 2005.0])),
        ("doy", np.array([355.0, 366.0, 355.0])),
        ("tt", np.array([54616.0, np.nan, 55252.0])),
        ("line", np.array([2004.0, np.inf, 2004.0])),
        ("N", 3.5),
        ("dt", -0.1),
    ],
)
@pytest.mark.parametrize("raw", [False, True])
def test_fill_and_allow_do_not_mask_corrupt_data(dataset_factory, field, value, raw):
    data = dataset_factory(lambda files: files[2005].update({field: value}))
    with pytest.raises(DataIntegrityError):
        data.read(
            Selection(2005),
            columns="mag_1_uc",
            missing="fill",
            empty="allow",
            raw=raw,
        )


def test_failures_validate_all_flights_before_download(tmp_path):
    data = Dataset(data_dir=tmp_path, offline=True)
    with pytest.raises(UnknownFlightError):
        data.fetch([2005, 9999])
    with pytest.raises(DataUnavailableError, match="offline mode"):
        data.fetch(2005)
    with pytest.raises(InvalidArgumentError):
        data.read([], columns="mag_1_uc")


def test_cross_collection_field_with_bad_shape_cannot_be_filled(dataset_factory):
    data = dataset_factory(lambda files: files[1002].update(flux_a_x=np.ones((5, 2))))
    with pytest.raises(DataIntegrityError, match="flux_a_x"):
        data.read(Selection(1002), columns="flux_a_x", missing="fill")


def test_empty_source_file_has_typed_output_and_no_time_range(dataset_factory):
    def empty_file(files):
        fields = files[1002]
        fields.pop("dt")
        fields["N"] = 0
        for name, values in fields.items():
            if isinstance(values, np.ndarray):
                fields[name] = values[:0]

    data = dataset_factory(empty_file)
    info = data.inspect(1002)
    assert info.sample_count == 0
    assert info.dt is None
    assert info.tt_range is None
    frame = data.read(Selection(1002), columns="all", empty="allow")
    assert frame.empty
    assert str(frame.time.dtype) == "datetime64[ns, UTC]"
    assert str(frame.mag_1_uc.dtype) == "float64"
