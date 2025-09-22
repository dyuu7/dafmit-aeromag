# DAF-MIT AeroMag

`dafmit-aeromag` is a Python interface to the DAF-MIT AIA open flight dataset for aircraft magnetic interference compensation and MagNav research. The package currently exposes Zenodo release **v3**, containing the 2020 and 2021 training flights.

This is an independent project and is not affiliated with or endorsed by the dataset authors or their institutions.

[English](README.md) | [简体中文](README.zh-CN.md) | [Documentation](https://dyuu7.github.io/dafmit-aeromag/)

The HDF5 files are not bundled in this repository. They are downloaded on first use into a configurable cache and verified against the checksums in the checked-in catalog.

## Install

```bash
python -m pip install dafmit-aeromag
```

For optional xarray conversion:

```bash
python -m pip install "dafmit-aeromag[xarray]"
```

## Quick start

```python
from dafmit_aeromag import Dataset, Selection

data = Dataset()

# Catalog queries do not download HDF5 data.
print(data.flights()[["flight", "collection", "date"]])
print(data.segments(2005, split="train"))
print(data.field_groups(flight=2005)[["group", "name", "units"]])

frame = data.read(
    Selection(flight=2005, lines=["2004.00"]),
    columns=["mag_1_uc", "ins_lat", "ins_lon"],
)
```

The normalized result starts with the stable identity columns `flight`, `line`, `year`, `doy`, `tt`, and `time`. Use `raw=True` when a consumer needs the source fields without derived identity columns:

```python
raw = data.read(
    [Selection.all(1002), Selection(flight=2005, tt=slice(54616, 55252))],
    columns=["mag_1_uc", "tt"],
    raw=True,
    missing="fill",
)
```

Selections are explicit and flight-scoped. Lines are decimal strings such as `"2005.20"`; time bounds are left-closed and right-open. The native `tt` coordinate and absolute `time` coordinate are alternative filters. Reads default to `split="train"`; pass `split="holdout"` for documented holdout intervals or `split="all"` to disable split filtering. Use `segments()` to inspect the source segment coverage.

## Why wrap this dataset?

The source release is authoritative and remains on Zenodo, but using it directly means coordinating large HDF5 files with separate readmes, field definitions, checksums, and train/holdout segment metadata. The 2020 and 2021 files also differ in schema, and a line label does not always identify the flight file that contains it.

This package brings those concerns into one reproducible interface: a versioned catalog pins exact source files, downloads are cached and verified, selections are explicitly scoped to a flight, split selection is explicit, and normalized identity and time columns make cross-collection analysis predictable. Field groups, notes, sensor positions, and source links help users discover the data without renaming or hiding the original HDF5 fields. Use `fetch()` when a workflow needs direct access to a verified local HDF5 file; the upstream field definitions remain authoritative.

## Data provenance and terms

The [Zenodo v3 record](https://zenodo.org/records/12723700) is authoritative for the released files, checksums, and release scope. Its readme snapshot is the primary semantic reference for this catalog; the pinned upstream [MagNav.jl](https://github.com/MIT-AI-Accelerator/MagNav.jl) revision is a stable, human-readable reference. The research data is subject to its own [Data Sharing Agreement](https://github.com/MIT-AI-Accelerator/MagNav.jl/blob/b79a9ceed6009878f47c72938718f96ce067d803/readmes/DATA_SHARING_AGREEMENT.md); that agreement is separate from this repository's MIT-licensed code. Read the [provenance and terms](docs/provenance-and-terms.en.md) page before using or redistributing any data-derived artifact.

## Documentation

The full API and maintenance notes are published at <https://dyuu7.github.io/dafmit-aeromag/> and are also available in [`docs/`](docs/).

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run pyright
uv run python scripts/check_i18n.py
uv run mkdocs build --strict
```

The project requires Python 3.10 or newer. The catalog updater fetches only Zenodo metadata and the small readme archives:

```bash
uv run python scripts/update_catalog.py
uv run python scripts/update_catalog.py --check
```
