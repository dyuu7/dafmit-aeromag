import pandas as pd
import pytest

from dafmit_aeromag import NoDataError, Selection


def test_read_keeps_samples_even_in_documented_holdout(synthetic_dataset):
    frame = synthetic_dataset.read(Selection.all(1002), columns="mag_1_uc")
    assert frame["tt"].tolist() == [45100.0, 45100.1, 45101.0, 45101.1, 56064.4]
    assert "split" not in frame.attrs


def test_columns_accept_series_and_normalized_time(synthetic_dataset):
    frame = synthetic_dataset.read(
        Selection(1002), columns=pd.Series(["time", "mag_1_uc", "time"])
    )
    assert frame.columns.tolist() == [
        "flight",
        "line",
        "year",
        "doy",
        "tt",
        "time",
        "mag_1_uc",
    ]


def test_empty_batch_entries_are_explicit(synthetic_dataset):
    query = [Selection(1002), Selection(2005, lines="9999")]
    with pytest.raises(NoDataError, match="selection 2"):
        synthetic_dataset.read(query, columns="mag_1_uc")
    frame = synthetic_dataset.read(query, columns="mag_1_uc", empty="allow")
    assert len(frame) == 5
    assert [item["row_count"] for item in frame.attrs["selections"]] == [5, 0]


def test_all_empty_has_complete_schema(synthetic_dataset):
    frame = synthetic_dataset.read(
        Selection(1002, lines="9999"), columns="mag_1_uc", empty="allow"
    )
    assert frame.empty
    assert str(frame.time.dtype) == "datetime64[ns, UTC]"
    assert str(frame.flight.dtype) == "int64"
    assert str(frame.mag_1_uc.dtype) == "float64"


def test_overlapping_selections_preserve_order_and_duplicates(synthetic_dataset):
    frame = synthetic_dataset.read(
        [Selection(1002, lines="1002.02"), Selection.all(1002)],
        columns="mag_1_uc",
    )
    assert frame.mag_1_uc.tolist() == [3.0, 4.0, 1.0, 2.0, 3.0, 4.0, 5.0]
