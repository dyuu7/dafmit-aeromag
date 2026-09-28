"""Exceptions raised by :mod:`dafmit_aeromag`."""


class DatasetError(Exception):
    """Base class for all expected library errors."""


class UnknownReleaseError(DatasetError):
    """The requested catalog release is not bundled with the package."""


class UnknownFlightError(DatasetError):
    """A flight identifier is not present in the selected release."""


class UnknownFieldError(DatasetError):
    """A field is absent from both the catalog and the selected files."""


class MissingFieldError(DatasetError):
    """A known field is unavailable in one or more selected flight files."""


class InvalidArgumentError(DatasetError, ValueError):
    """An argument has an invalid type, value, or combination of constraints."""


class DataIntegrityError(DatasetError):
    """A local or downloaded data file failed an integrity check."""


class DataUnavailableError(DatasetError):
    """A requested data file could not be made available."""


class NoDataError(DatasetError):
    """A valid selection contains no samples."""
