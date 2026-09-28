from __future__ import annotations

import numpy as np
import pytest

from dafmit_aeromag import InvalidArgumentError, Selection


def test_selection_normalises_lines_and_is_immutable() -> None:
    selection = Selection(2005, lines=["2005.2", "2005.20", "2005.21"])

    assert selection.lines == ("2005.20", "2005.21")
    assert Selection.all(1002).lines is None
    assert Selection(np.int64(1002)).flight == 1002


@pytest.mark.parametrize("value", [2005.2, "2005.*", "2005.20:2005.22"])
def test_selection_rejects_ambiguous_line_syntax(value: object) -> None:
    with pytest.raises(InvalidArgumentError):
        Selection(2005, lines=value)  # type: ignore[arg-type]


def test_selection_rejects_two_time_coordinates() -> None:
    with pytest.raises(InvalidArgumentError, match="mutually exclusive"):
        Selection(1002, time=slice("2020-01-01", None), tt=slice(1, 2))


def test_selection_rejects_step_and_reversed_slices() -> None:
    with pytest.raises(InvalidArgumentError):
        Selection(1002, tt=slice(1, 2, 1))
    with pytest.raises(InvalidArgumentError):
        Selection(1002, tt=slice(2, 1))
    with pytest.raises(InvalidArgumentError):
        Selection(1002, time=slice("2020-01-02", "2020-01-01"))


@pytest.mark.parametrize(
    "value",
    [slice("NaT", "2020-01-02"), slice("2020-01-01", "NaT")],
)
def test_selection_rejects_nat_time_bounds(value: slice) -> None:
    with pytest.raises(InvalidArgumentError, match="valid timestamps"):
        Selection(1002, time=value)


@pytest.mark.parametrize("bound", [np.nan, np.inf, -np.inf])
def test_selection_rejects_nonfinite_tt_bounds(bound: float) -> None:
    with pytest.raises(InvalidArgumentError, match="finite"):
        Selection(1002, tt=slice(bound, None))


@pytest.mark.parametrize("bound", ["invalid", "NaT", np.datetime64("NaT", "ns")])
@pytest.mark.parametrize("left", [True, False])
def test_invalid_open_time_bounds_fail_at_construction(bound, left):
    interval = slice(bound, None) if left else slice(None, bound)
    with pytest.raises(InvalidArgumentError, match="valid timestamps"):
        Selection(1002, time=interval)


def test_time_and_line_inputs_are_normalized_once():
    from dataclasses import FrozenInstanceError

    import pandas as pd

    names = (value for value in ["1002.1", "1002.10", "1002.2"])
    selection = Selection(
        1002, lines=names, time=slice(np.datetime64("2020-06-20"), None)
    )
    assert selection.lines == ("1002.10", "1002.20")
    assert selection.time.start == pd.Timestamp("2020-06-20", tz="UTC")
    assert Selection(1002, lines=pd.Series(["1002.1"])).lines == ("1002.10",)
    assert Selection(1002, lines=np.array(["1002.1"])).lines == ("1002.10",)
    with pytest.raises(FrozenInstanceError):
        selection.flight = 2005


@pytest.mark.parametrize("value", [True, 0, -1, 1002.0, "1002", None])
def test_flight_identifiers_are_positive_integers(value):
    with pytest.raises(InvalidArgumentError):
        Selection(value)


@pytest.mark.parametrize("value", [set(["1002.01"]), {"1002.01": 1}, [], b"1002.01"])
def test_unordered_and_empty_lines_are_rejected(value):
    with pytest.raises(InvalidArgumentError):
        Selection(1002, lines=value)
