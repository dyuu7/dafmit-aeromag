from collections.abc import Iterable, Mapping, Set
from numbers import Integral
from typing import TypeVar, cast

from .exceptions import InvalidArgumentError

T = TypeVar("T")


def ordered_values(value: Iterable[T], name: str) -> tuple[T, ...]:
    """Consume an ordered iterable once, rejecting ambiguous containers."""
    if isinstance(value, (str, bytes, bytearray, Mapping, Set)):
        raise InvalidArgumentError(f"{name} must be an ordered iterable")
    try:
        return tuple(value)
    except TypeError as exc:
        raise InvalidArgumentError(f"{name} must be an ordered iterable") from exc


def flight_id(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 1:
        raise InvalidArgumentError("flight must be a positive integer identifier")
    return int(value)


def flight_ids(value: int | Iterable[int]) -> tuple[int, ...]:
    if isinstance(value, bool):
        raise InvalidArgumentError("flight must be a positive integer identifier")
    values = (
        (int(value),)
        if isinstance(value, Integral)
        else ordered_values(cast(Iterable[int], value), "flights")
    )
    if not values:
        raise InvalidArgumentError("flights cannot be empty")
    return tuple(dict.fromkeys(flight_id(item) for item in values))


def field_names(value: str | Iterable[str]) -> tuple[str, ...]:
    values = (value,) if isinstance(value, str) else ordered_values(value, "columns")
    if any(not isinstance(item, str) or not item for item in values):
        raise InvalidArgumentError("column names must be non-empty strings")
    return tuple(dict.fromkeys(values))
