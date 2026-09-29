# API

See the [quickstart](quickstart.md) for a complete workflow and the [data model](data-model.md) for ordering, field, and verification contracts. All documented types and errors below are importable from `dafmit_aeromag`.

## Errors

All domain errors inherit from `DatasetError`. `InvalidArgumentError` also inherits from `ValueError`. Unsupported keyword arguments use Python's normal `TypeError`.

| Error | Meaning / next step |
| --- | --- |
| `UnknownReleaseError` | Choose a bundled release (`v3`) |
| `UnknownFlightError` | Inspect `flights()` for valid file identifiers |
| `UnknownFieldError` | Check spelling, field definitions, and actual file inspection |
| `MissingFieldError` | A recognized field is absent; choose another field or explicitly fill |
| `InvalidArgumentError` | Correct the reported input type, value, or combination |
| `DataUnavailableError` | A local file is missing/unreadable or a download cannot complete |
| `DataIntegrityError` | Bytes, structure, or coordinates fail verification, or a file changed during a read |
| `NoDataError` | A selection matches no samples; revise it or explicitly allow empty results |

## Public interface

::: dafmit_aeromag.Dataset
    options:
      show_root_heading: true
      show_object_full_path: false

::: dafmit_aeromag.Selection
    options:
      show_root_heading: true
      show_object_full_path: false

::: dafmit_aeromag.FlightInfo
    options:
      show_root_heading: true
      show_object_full_path: false

::: dafmit_aeromag.DatasetError
    options:
      show_root_heading: true
      show_object_full_path: false

::: dafmit_aeromag.InvalidArgumentError
    options:
      show_root_heading: true
      show_object_full_path: false
