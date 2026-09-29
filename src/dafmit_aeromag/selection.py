from __future__ import annotations

from collections.abc import Iterable
from dataclasses import KW_ONLY, dataclass
from datetime import date, datetime
from decimal import Decimal
from math import isfinite
from numbers import Real
from re import fullmatch

import numpy as np
import pandas as pd

from ._validation import flight_id, ordered_values
from .exceptions import InvalidArgumentError


def canonical_line(value: str) -> str:
    """Normalize a decimal string without accepting ambiguous floating inputs."""
    if (
        not isinstance(value, str)
        or fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", value.strip()) is None
    ):
        raise InvalidArgumentError(
            "lines must be decimal strings such as '2005.20'; "
            "wildcards, ranges, and numeric floats are not supported"
        )
    return f"{Decimal(value.strip()):.2f}"


def _normalise_lines(value: str | Iterable[str] | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    values = (value,) if isinstance(value, str) else ordered_values(value, "lines")
    if not values:
        raise InvalidArgumentError("lines cannot be empty")
    return tuple(dict.fromkeys(canonical_line(item) for item in values))


def _normalise_range(value: slice | None, coordinate: str) -> slice | None:
    if value is None:
        return None
    if not isinstance(value, slice) or value.step is not None:
        raise InvalidArgumentError(f"{coordinate} must be a slice with no step")
    if value.start is None and value.stop is None:
        raise InvalidArgumentError(f"{coordinate} needs at least one bound")
    bounds = []
    for bound in (value.start, value.stop):
        if bound is None:
            bounds.append(None)
        elif coordinate == "tt":
            if isinstance(bound, bool) or not isinstance(bound, Real):
                raise InvalidArgumentError("tt bounds must be finite numbers")
            try:
                number = float(bound)
            except (ValueError, OverflowError) as exc:
                raise InvalidArgumentError("tt bounds must be finite numbers") from exc
            if not isfinite(number):
                raise InvalidArgumentError("tt bounds must be finite numbers")
            bounds.append(number)
        else:
            if not isinstance(bound, (str, date, datetime, np.datetime64)):
                raise InvalidArgumentError("time bounds must be valid timestamps")
            try:
                stamp = pd.Timestamp(bound)
                if not isinstance(stamp, pd.Timestamp):
                    raise ValueError("NaT is not a time bound")
                stamp = (
                    stamp.tz_localize("UTC")
                    if stamp.tzinfo is None
                    else stamp.tz_convert("UTC")
                )
            except (TypeError, ValueError, OverflowError) as exc:
                raise InvalidArgumentError(
                    "time bounds must be valid timestamps"
                ) from exc
            bounds.append(stamp)
    if bounds[0] is not None and bounds[1] is not None and bounds[0] >= bounds[1]:
        raise InvalidArgumentError(
            f"{coordinate} uses left-closed, right-open bounds: start < stop"
        )
    return slice(*bounds)


@dataclass(frozen=True, slots=True)
class Selection:
    """Select samples from one flight by line and/or a time range.

    Parameters
    ----------
    flight:
        File/flight identifier, independent of the line label.
    lines:
        One decimal string or an ordered iterable of strings. Duplicates are removed.
    tt:
        Native seconds past midnight, as ``slice(start, stop)``.
    time:
        Absolute timestamps, as ``slice(start, stop)``. Naive bounds mean UTC.

    Notes
    -----
    Both ranges include the start and exclude the stop. ``tt`` and ``time`` are
    mutually exclusive. Bounds are validated when the selection is constructed.
    """

    flight: int
    _: KW_ONLY
    lines: str | Iterable[str] | None = None
    tt: slice | None = None
    time: slice | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "flight", flight_id(self.flight))
        if self.tt is not None and self.time is not None:
            raise InvalidArgumentError("time and tt are mutually exclusive")
        object.__setattr__(self, "lines", _normalise_lines(self.lines))
        object.__setattr__(self, "tt", _normalise_range(self.tt, "tt"))
        object.__setattr__(self, "time", _normalise_range(self.time, "time"))

    @classmethod
    def all(cls, flight: int) -> Selection:
        """Select every sample physically present in the flight file."""
        return cls(flight)
