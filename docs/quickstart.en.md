# Quickstart

## Inspect the catalog

Catalog methods read the bundled JSON manifest and do not download HDF5 files.

```python
from dafmit_aeromag import Dataset

data = Dataset(offline=True)
data.flights()
data.fields(flight=2005)
data.field_groups(flight=2005)
data.field_names("scalar_magnetometer", flight=2005)
data.sensors(collection="2021")
data.segments(2005, split="train")
```

`offline=True` is useful in review environments and reproducible jobs. It allows catalog inspection and local reads, but raises a clear error if a file is missing.

## Read normalized data

```python
from dafmit_aeromag import Dataset, Selection

data = Dataset(data_dir="./data")
selection = Selection(flight=2005, lines=["2004.00"])
frame = data.read(
    selection,
    columns=["mag_1_uc", "ins_lat", "ins_lon"],
)
```

The first columns are always `flight`, `line`, `year`, `doy`, `tt`, and `time`. `time` is UTC; naive time bounds are interpreted as UTC, and the value is derived from the flight date and native timing fields when a source file does not store complete identity fields.

## Read more than one flight

```python
frame = data.read(
    [Selection.all(1002), Selection(flight=2005, tt=slice(54616, 55252))],
    columns=["mag_1_uc", "ins_lat"],
    missing="fill",
)
```

Rows follow selection order and then source order. `missing="raise"` is the default for an explicit column list. Use `missing="fill"` when intentionally combining fields from the 2020 and 2021 schemas.

## Choose a data split

`read()` defaults to the catalogued training intervals. Holdout data and the unfiltered source view are explicit:

```python
train = data.read(selection, columns=["mag_1_uc"], split="train")
holdout = data.read(selection, columns=["mag_1_uc"], split="holdout")
all_samples = data.read(selection, columns=["mag_1_uc"], split="all")
```

Use `Dataset.segments()` before a split-specific read when you need to inspect the source line and time boundaries. Field groups are discovery helpers; use `Dataset.fields()` and the linked upstream readmes for full field semantics.

## Access the verified source file

When a workflow needs HDF5-specific features or fields outside the normalized reader, use `fetch()` and open the returned path with your preferred HDF5 tool:

```python
paths = data.fetch(2005)
source_path = paths[2005]
```

The returned file has passed the catalogued size, checksum, and HDF5 readability checks.

## Native fields and xarray

Use `raw=True` to omit derived identity columns:

```python
raw = data.read(selection, columns=["tt", "mag_1_uc"], raw=True)
```

Install the optional extra and convert a returned frame when an xarray data model is more convenient:

```bash
python -m pip install "dafmit-aeromag[xarray]"
```

```python
dataset = data.to_xarray(frame)
```
