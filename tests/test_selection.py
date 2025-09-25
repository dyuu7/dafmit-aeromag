from __future__ import annotations

import numpy as np
import pytest

from dafmit_aeromag import InvalidSelectionError, Selection


def test_selection_normalises_lines_and_is_immutable() -> None:
    selection = Selection(2005, lines=["2005.2", "2005.20", "2005.21"])

    assert selection.lines == ("2005.20", "2005.21")
    assert Selection.all(1002).lines is None
    assert Selection(np.int64(1002)).flight == 1002


@pytest.mark.parametrize("value", [2005.2, "2005.*", "2005.20:2005.22"])
def test_selection_rejects_ambiguous_line_syntax(value: object) -> None:
    with pytest.raises(InvalidSelectionError):
        Selection(2005, lines=value)  # type: ignore[arg-type]


def test_selection_rejects_two_time_coordinates() -> None:
    with pytest.raises(InvalidSelectionError, match="mutually exclusive"):
        Selection(1002, time=slice("2020-01-01", None), tt=slice(1, 2))


def test_selection_rejects_step_and_reversed_slices() -> None:
    with pytest.raises(InvalidSelectionError):
        Selection(1002, tt=slice(1, 2, 1))
    with pytest.raises(InvalidSelectionError):
        Selection(1002, tt=slice(2, 1))
    with pytest.raises(InvalidSelectionError):
        Selection(1002, time=slice("2020-01-02", "2020-01-01"))


@pytest.mark.parametrize(
    "value",
    [slice("NaT", "2020-01-02"), slice("2020-01-01", "NaT")],
)
def test_selection_rejects_nat_time_bounds(value: slice) -> None:
    with pytest.raises(InvalidSelectionError, match="valid timestamps"):
        Selection(1002, time=value)


@pytest.mark.parametrize("bound", [np.nan, np.inf, -np.inf])
def test_selection_rejects_nonfinite_tt_bounds(bound: float) -> None:
    with pytest.raises(InvalidSelectionError, match="finite"):
        Selection(1002, tt=slice(bound, None))
