# Quickstart

## Discover the release without downloading data

A `Dataset` represents one published release. A **collection** is the survey year (`"2020"` or `"2021"`); a **flight** identifies one file; a **line** labels measurements within that file. A line label need not start with its file's flight number: flight 2005 contains line `"2004.00"`.

```python
from dafmit_aeromag import Dataset, Selection

data = Dataset(data_dir="./data")
data.flights()
data.fields(flight=2005)
data.field_groups(collection="2021")
data.field_names(flight=2005, group="scalar_magnetometer")
data.sensors(flight=2005)
data.segments(2005)
```

These methods use the bundled catalog and never download data. In field and sensor queries, supply either `flight=` or `collection=`, or omit both to see all collections. `fields(flight=2005)` returns that collection's **documented definitions**, not a promise that every field exists in this flight.

`segments()` reports the intervals described in the upstream readmes. Its `is_holdout` column preserves an upstream evaluation annotation. It is not a quality flag or a statement that those samples are included in the published file. Reading does not apply these annotations as filters.

## Inspect a real file, then read it

```python
info = data.inspect(2005)
print(info.sample_count)  # 6361 in the pinned v3 file
print(info.tt_range)  # (54616.0, 55252.0), inclusive observed extrema
print(info.fields[["name", "dtype", "units"]])

frame = data.read(
    Selection(flight=2005, lines="2004.00"),
    columns=["mag_1_uc", "ins_lat", "ins_lon"],
)
```

`inspect()` and `read()` download a missing file and verify it against the catalog. Reuse the same `Dataset` to avoid repeating the checksum for unchanged files. To prohibit downloads, construct it with `offline=True`; missing local files then raise `DataUnavailableError`.

Use the default cache on a personal machine. Colleagues may also download into one shared directory; the library coordinates the first download of each file. For read-only access, use offline mode:

```python
personal = Dataset()
shared = Dataset(data_dir="/mnt/lab/dafmit-aeromag")
shared_read_only = Dataset(data_dir="/mnt/lab/dafmit-aeromag", offline=True)
```

A writable shared directory must support cross-process file locks and allow users to create files, read each other's data files, and read/write each other's lock files. New files follow the process umask and inherited directory ACLs. On Unix, use a shared group with a setgid directory and `umask 0007`, or configure default ACLs. An existing file that fails verification raises an error; it is not replaced automatically.

Reads return a pandas `DataFrame`. The normalized frame starts with `flight`, `line`, `year`, `doy`, `tt`, and `time`. `line` contains decimal strings. `tt` is the source's seconds past midnight; `time` is a UTC timestamp. Missing source identity fields are derived from the catalog's flight date and identifier. Measurements retain their source names and units.

## Choose samples explicitly

```python
all_samples = data.read(Selection.all(2005), columns="mag_1_uc")
bounded = data.read(
    Selection(2005, tt=slice(54616, 55252)),
    columns="mag_1_uc",
)
assert len(all_samples) == 6361
assert len(bounded) == 6360

by_time = data.read(
    Selection(2005, time=slice("2021-12-21T15:10:16Z", "2021-12-21T15:11:00Z")),
    columns="mag_1_uc",
)
```

A range includes its start and excludes its stop: `slice(a, b)` means `a <= coordinate < b`. Either bound can be `None`, but not both. `tt` and `time` are alternatives. A line constraint and a time constraint select their intersection. Time bounds without a timezone mean UTC; explicit offsets are converted to UTC.

The last sample above is present in the file. Only the explicit `tt` range excludes it. Define training and evaluation subsets using explicit flight, line, and time constraints in your experiment. See the [file audit](data-audit.md) for the evidence.

## Choose fields and handle schema differences

```python
# Six identity columns only; useful for coverage analysis.
coordinates = data.read(Selection(2005), columns=[])

# Every physical sample field, plus normalized identity columns.
everything = data.read(Selection(2005), columns="all")

# A catalog query can feed directly into a read.
names = data.field_names(flight=2005, group="scalar_magnetometer")
magnetic = data.read(Selection(2005), columns=names, missing="fill")

# Actual fields are directly usable; scalar HDF5 metadata is excluded.
native = data.read(Selection(2005), columns=info.fields.name, raw=True)
```

`columns` is required. It accepts one name, an ordered iterable of names, or `"all"`. Lists, tuples, pandas Series/Index, one-dimensional NumPy arrays, and generators work; sets and mappings are rejected. Duplicate names are removed in first-seen order.

`missing="raise"` is the default. `missing="fill"` supplies `NaN` for a recognized field absent from a file. A typo still raises `UnknownFieldError`, and malformed data still raises `DataIntegrityError`. `raw=True` returns only physical fields: it cannot request derived `time` or an empty column list.

## Combine selections and make empty results explicit

```python
combined = data.read(
    [Selection(1004, lines="1004.02"), Selection.all(2005)],
    columns=["mag_1_uc", "flux_a_x"],
    missing="fill",
)

documented_but_absent = data.read(
    Selection(1004, lines="4014.00"),
    columns="mag_1_uc",
    empty="allow",
)
assert documented_but_absent.empty
print(combined.attrs["selections"])
```

Rows follow selection order, then source row order. Overlapping selections preserve duplicates. By default **any** empty selection raises `NoDataError`, including one empty member of an otherwise successful batch. `empty="allow"` preserves the full schema even if the whole result is empty. Each selection's `row_count` is recorded in `frame.attrs["selections"]`, including zeroes.

## Access the source file

```python
source_path = data.fetch(2005)[2005]
data.fetch(2005, recheck=True)  # Force a fresh size/checksum/structure check.
```

Open `source_path` with h5py when you need scalar metadata (`N`, `dt`, `info`) or other HDF5 features. `inspect().dt` is the declared sampling interval; it does not guarantee continuous coverage.
