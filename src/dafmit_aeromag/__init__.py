"""Access to the open MIT-AI-Accelerator flight data releases."""

from .dataset import Dataset
from .exceptions import (
    DataIntegrityError,
    DatasetError,
    DataUnavailableError,
    InvalidSelectionError,
    MissingFieldError,
    NoDataError,
    UnknownFieldError,
    UnknownFlightError,
    UnknownReleaseError,
)
from .selection import Selection

__all__ = [
    "DataIntegrityError",
    "DataUnavailableError",
    "Dataset",
    "DatasetError",
    "InvalidSelectionError",
    "MissingFieldError",
    "NoDataError",
    "Selection",
    "UnknownFieldError",
    "UnknownFlightError",
    "UnknownReleaseError",
]

__version__ = "0.3.0"
