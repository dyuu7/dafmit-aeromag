# DAF-MIT AeroMag

`dafmit-aeromag` is a Python interface to the DAF-MIT AIA open flight dataset for aircraft magnetic interference compensation and magnetic navigation research. It pins Zenodo release **v3**, containing 16 published flight files from 2020 and 2021.

[English](README.md) | [简体中文](README.zh-CN.md) | [Documentation](https://dyuu7.github.io/dafmit-aeromag/)

This is an independent project, not affiliated with or endorsed by the dataset authors or their institutions. Large HDF5 files are downloaded on demand into a configurable cache and checked against the bundled release manifest.

## Install

Requires Python 3.10 or newer:

```bash
python -m pip install dafmit-aeromag
```

## Discover, inspect, read

```python
from dafmit_aeromag import Dataset, Selection

data = Dataset(data_dir="./data")

# Offline discovery: documented definitions and segment annotations.
print(data.flights()[["flight", "collection", "date"]])
print(data.fields(flight=2005)[["name", "units", "description"]])
print(data.field_groups(flight=2005))
print(data.segments(2005))

# Physical inspection: download if missing, verify, then report real fields.
info = data.inspect(2005)
print(info.sample_count)  # 6361
print(info.fields[["name", "dtype", "units"]])

frame = data.read(
    Selection(flight=2005, lines="2004.00"),
    columns=["mag_1_uc", "ins_lat", "ins_lon"],
)
```

A flight identifies a file; a line is a label inside it and can use a different number. Reads return a pandas `DataFrame`; the normalized result starts with `flight`, `line`, `year`, `doy`, `tt`, and UTC `time`. Specify one field, an ordered iterable, `columns="all"` for all physical fields, or `columns=[]` for identity columns only.

Reads return actual samples matching your selection. There is **no automatic train/holdout filtering**. Upstream filenames retain `_train.h5`, and `segments().is_holdout` preserves the upstream annotation; it does not imply poor quality or physical availability. Define training and evaluation subsets in your experiment. The [file audit](docs/data-audit.en.md) documents actual sample coverage and selection boundaries.

## Explicit ranges and batch behavior

```python
frame = data.read(
    [Selection.all(1004), Selection(2005, tt=slice(54616, 55252))],
    columns=["mag_1_uc", "flux_a_x"],
    missing="fill",
)
```

Time ranges include the start and exclude the stop. Native `tt` (seconds past midnight) and absolute `time` are alternative filters. Rows follow query order and source order; overlapping queries preserve duplicates. By default each query must return samples. Use `empty="allow"` when empty selections are expected, and inspect `frame.attrs["selections"]` for their row counts.

`missing="fill"` fills absent recognized fields with `NaN`; unknown names and malformed data still raise errors. `fields()` describes the collection, while `inspect(flight).fields` reports actual fields. This distinction matters when combining the two collection schemas.

## Native fields and source files

```python
raw = data.read(Selection(2005), columns=["tt", "mag_1_uc"], raw=True)
source_path = data.fetch(2005)[2005]
```

Raw reads omit derived columns. Use the verified path for direct HDF5 access. Reusing one `Dataset` reuses successful checks while the file's filesystem state is unchanged; `fetch(2005, recheck=True)` forces a full recheck. Set `offline=True` when constructing the dataset to prohibit downloads.

## Documentation and provenance

Start with the [quickstart](docs/quickstart.en.md) and [data model](docs/data-model.en.md). The published [documentation site](https://dyuu7.github.io/dafmit-aeromag/) includes the API reference and maintenance guide.

The [Zenodo v3 record](https://zenodo.org/records/12723700) is authoritative for files, checksums, and release scope. Its readme snapshot supplies the catalog semantics; a pinned [MagNav.jl revision](https://github.com/MIT-AI-Accelerator/MagNav.jl/tree/b79a9ceed6009878f47c72938718f96ce067d803/readmes) provides stable source links. The research data has its own [Data Sharing Agreement](https://github.com/MIT-AI-Accelerator/MagNav.jl/blob/b79a9ceed6009878f47c72938718f96ce067d803/readmes/DATA_SHARING_AGREEMENT.md), separate from this repository's MIT code license. See [provenance and terms](docs/provenance-and-terms.en.md) for details.

## Development

```bash
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python scripts/check_i18n.py
uv run mkdocs build --strict
uv run python -m build
```

Ordinary tests run offline. Real-file tests and catalog regeneration are documented in the [maintenance guide](docs/maintenance.en.md).
