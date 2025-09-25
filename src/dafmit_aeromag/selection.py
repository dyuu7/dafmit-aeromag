"""Typed query objects used by :class:`~dafmit_aeromag.Dataset`."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from math import isfinite
from numbers import Integral, Real
from re import fullmatch

import pandas as pd

from .exceptions import InvalidSelectionError

_LINE_PATTERN = r"[0-9]+(?:\.[0-9]{1,2})?"


def canonical_line(value: str) -> str:
    """Return the two-decimal representation used by the flight readmes."""

    if not isinstance(value, str) or fullmatch(_LINE_PATTERN, value.strip()) is None:
        raise InvalidSelectionError(
            "lines must be decimal strings such as '2005.20'; wildcards, "
            "ranges, and numeric floats are not supported"
        )
    try:
        number = Decimal(value.strip())
    except InvalidOperation as exc:  # pragma: no cover - guarded by the regex
        raise InvalidSelectionError(f"invalid line {value!r}") from exc
    return f"{number:.2f}"


def _normalise_lines(value: str | Sequence[str] | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, str):
        values = (value,)
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        values = tuple(value)
    else:
        raise InvalidSelectionError("lines must be a string or a sequence of strings")
    if not values:
        raise InvalidSelectionError("lines cannot be empty")
    normalised = tuple(canonical_line(item) for item in values)
    return tuple(dict.fromkeys(normalised))


def _normalise_tt(value: slice | None) -> slice | None:
    if value is None:
        return None
    if not isinstance(value, slice) or value.step is not None:
        raise InvalidSelectionError("tt must be a slice with no step")
    bounds: list[float | None] = []
    for bound in (value.start, value.stop):
        if bound is None:
            bounds.append(None)
        elif isinstance(bound, Real) and not isinstance(bound, bool):
            try:
                number = float(bound)
            except (TypeError, ValueError, OverflowError) as exc:
                raise InvalidSelectionError("tt bounds must be finite numbers") from exc
            if not isfinite(number):
                raise InvalidSelectionError("tt bounds must be finite numbers")
            bounds.append(number)
        else:
            raise InvalidSelectionError("tt bounds must be numbers or None")
    if bounds[0] is None and bounds[1] is None:
        raise InvalidSelectionError("tt needs at least one bound")
    if bounds[0] is not None and bounds[1] is not None and bounds[0] >= bounds[1]:
        raise InvalidSelectionError(
            "tt uses left-closed, right-open bounds: start < stop"
        )
    return slice(bounds[0], bounds[1])


def _normalise_time(value: slice | None) -> slice | None:
    if value is None:
        return None
    if not isinstance(value, slice) or value.step is not None:
        raise InvalidSelectionError("time must be a slice with no step")
    for bound in (value.start, value.stop):
        if bound is not None and not isinstance(bound, (str, date, datetime)):
            raise InvalidSelectionError(
                "time bounds must be ISO strings or date objects"
            )
    if value.start is None and value.stop is None:
        raise InvalidSelectionError("time needs at least one bound")
    if value.start is not None and value.stop is not None:
        try:
            start = pd.Timestamp(value.start)
            stop = pd.Timestamp(value.stop)
        except (TypeError, ValueError, OverflowError) as exc:
            raise InvalidSelectionError("time bounds must be valid timestamps") from exc
        if not isinstance(start, pd.Timestamp) or not isinstance(stop, pd.Timestamp):
            raise InvalidSelectionError("time bounds must be valid timestamps")
        if start.tzinfo is None:
            start = start.tz_localize("UTC")
        else:
            start = start.tz_convert("UTC")
        if stop.tzinfo is None:
            stop = stop.tz_localize("UTC")
        else:
            stop = stop.tz_convert("UTC")
        if start >= stop:
            raise InvalidSelectionError(
                "time uses left-closed, right-open bounds: start < stop"
            )
    return value


@dataclass(frozen=True, slots=True)
class Selection:
    """A flight-scoped sample selection.

    ``lines`` accepts canonical decimal strings. ``time`` and ``tt`` are
    half-open slices, and are intentionally mutually exclusive because ``tt``
    is the native time coordinate stored by the source files.
    """

    flight: int
    lines: str | Sequence[str] | None = None
    time: slice | None = None
    tt: slice | None = None

    def __post_init__(self) -> None:
        if isinstance(self.flight, bool) or not isinstance(self.flight, Integral):
            raise InvalidSelectionError("flight must be an integer identifier")
        flight = int(self.flight)
        if flight < 1:
            raise InvalidSelectionError("flight must be positive")
        object.__setattr__(self, "flight", flight)
        if self.time is not None and self.tt is not None:
            raise InvalidSelectionError("time and tt are mutually exclusive")
        object.__setattr__(self, "lines", _normalise_lines(self.lines))
        object.__setattr__(self, "time", _normalise_time(self.time))
        object.__setattr__(self, "tt", _normalise_tt(self.tt))

    @classmethod
    def all(cls, flight: int) -> Selection:
        """Select every sample in ``flight`` before the read split is applied."""

        return cls(flight=flight)
