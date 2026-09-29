# Data model

## Published data, documentation, and experiments

The package pins Zenodo release **v3**, record [`12723700`](https://zenodo.org/records/12723700), with 16 flight files from the 2020 and 2021 collections. These are published subsets of airborne time series. Their upstream filenames end in `_train.h5`; the package preserves those names and checksums.

Three kinds of information have different responsibilities:

| Information | Authority | Interface |
| --- | --- | --- |
| Samples and fields actually present | Verified HDF5 file | `inspect()`, `read()`, `fetch()` |
| Field meanings, sensor positions, documented segments | Release readmes | `fields()`, `sensors()`, `segments()` |
| Your training/validation/test partition | Your experiment design | Explicit `Selection` objects and downstream analysis |

`is_holdout` means that the upstream segment description contains a holdout annotation. Holdout means reserved for evaluation; it does **not** mean invalid or worthless data. Neither `True` nor `False` establishes physical availability. A documented interval can contain no released samples. A repeated line label also need not have one consistent annotation. Sample coverage is determined by the actual file, and training/evaluation subsets are defined by explicit selections in your experiment. See the [actual file audit](data-audit.md).

## Catalog discovery and physical inspection

`flights()`, `fields()`, `field_names()`, `field_groups()`, `sensors()`, `segments()`, and `metadata` operate offline. `fields`, `field_names`, `field_groups`, and `sensors` accept keyword-only `flight` or `collection` scope; supplying both is an error. A flight scope selects its collection's definitions. `fields()` and `field_names()` additionally accept `group=`.

`fields()` contains one row per collection and field: `collection`, `name`, `units`, `description`, `group`, `notes`, and `source_url`. With no collection restriction, the same name can appear in both collections. `field_names()` returns a tuple of names deduplicated in first-seen order. `field_groups()` returns a summary with `group`, `description`, and `field_count`; this count is the number of unique names in the chosen scope.

`segments(flights=None)` preserves readme start/end values without imposing a universal endpoint convention. Rows contain flight, segment ordinal, line label, start/end seconds, description, `is_holdout`, and source URL. `segments([1004, 2005])` restricts the flights. Segment ordinals distinguish repeated line labels; these rows never define an automatic sample mask.

`inspect(flight)` accesses the verified file and returns `FlightInfo`:

| Attribute | Meaning |
| --- | --- |
| `flight`, `path` | Flight identifier and verified local file path |
| `sample_count` | Number of actual samples |
| `dt` | Declared interval in seconds, or `None` if absent |
| `tt_range` | Observed minimum and maximum, both inclusive; `None` if empty |
| `fields` | Actual one-dimensional sample fields, with dtype and available documentation |

Inspection includes undocumented physical sample fields. For example, the 2020 field readme defines 99 fields, but the inspected Flt1004 file contains 96: `year`, `doy`, and `mag_6_uc` are absent. Catalog discovery and file inspection answer different questions.

`Dataset` keeps its catalog private. Public metadata dictionaries and tables are detached copies, including nested notes. Changing them does not alter another query or instance. Configuration (`release`, `data_dir`, `offline`, `progress`) is read-only; construct another instance to change it. An inspection report's field table is also detached.

## Selection and ordering

`Selection` is immutable. Only `flight` can be positional; `lines`, `tt`, and `time` are keyword-only. `Selection.all(2005)` and `Selection(2005)` both select all samples in that file.

Line labels are decimal strings normalized to two places; floats, wildcards, and line ranges are rejected. Repeated line constraints are removed. Both time coordinates use `start <= value < stop`, permit one open bound, reject invalid/nonfinite bounds and steps, and require start before stop when both are given. `time` and `tt` cannot be combined; lines can be combined with either. Naive absolute times mean UTC.

Reads preserve selection order and then source order. A list of lines is a membership condition, not a request to reorder the file. There is no implicit sorting, resampling, interpolation, or deduplication of samples. Overlapping selections retain duplicates. Do not assume that a declared `dt` or a file's minimum/maximum implies uninterrupted coverage.

## Columns, types, and failures

`read(..., columns=...)` requires a field choice. A string requests one name; `"all"` requests the union of physical sample fields across selected files. An ordered iterable requests those names in first-seen order. Normalized output has this fixed prefix:

| Column | Type and meaning |
| --- | --- |
| `flight` | `int64`, file/flight identifier |
| `line` | pandas string dtype, canonical line label |
| `year` | `int64`, UTC year |
| `doy` | `int64`, UTC day of year, starting at 1 |
| `tt` | `float64`, native seconds past midnight |
| `time` | `datetime64[ns, UTC]`, year/day plus native seconds |

Absent source `flight`, `year`, or `doy` is derived from the pinned flight metadata. Present identity values must be valid; the reader does not overwrite malformed values with defaults. `columns=[]` returns just this prefix. Explicitly requested identity names are not duplicated.

`raw=True` returns only physical fields, including numeric source line labels, without derived columns. It still applies selection and integrity checks. Raw reads reject `columns=[]` and derived `time`; absent source identity fields follow the normal missing-field policy. Scalar `N`, `dt`, and `info` are never sample columns. Use `fetch()` for direct HDF5 access.

A missing field is recognized in the catalog or another selected file but absent from one file. `missing="raise"` rejects it; `missing="fill"` supplies `NaN`. Integer measurement columns may become floating point to represent `NaN`, and batches use a common type across files. Unknown names raise `UnknownFieldError` even with filling enabled. A present documented sample field with the wrong shape raises `DataIntegrityError`; filling cannot hide it. Physically present undocumented sample fields are readable, with blank documentation where none exists. Conflicting documented units across selected collections raise `InvalidArgumentError`; no unit conversion is guessed.

`empty="raise"` rejects every empty selection individually with `NoDataError`. `empty="allow"` permits them; even a fully empty result has all requested columns and their planned types. An empty batch of selections is an invalid argument, rather than an empty read.

## Result metadata

`frame.attrs` contains `release`, `doi`, `record_id`, `raw`, `flights`, `units`, and `selections`. Each selection records its normalized flight/line/time constraints and `row_count`, including zero for allowed empty selections. Absolute bounds are ISO timestamp strings. This is a record of the read; arbitrary downstream pandas operations are not guaranteed to maintain or update it.

## Verification and resource lifetime

Files are downloaded on demand into `data_dir`. Before first use by a `Dataset`, the store checks byte size, MD5 checksum, HDF5 readability, mandatory coordinate shapes, and declared scalar metadata. Reading/inspection additionally validates sample-field shapes and coordinate values. These checks establish agreement with the pinned release and structural validity, not scientific quality of every measurement.

Successful verification is reused only inside that instance while the file's device, inode, size, and nanosecond modification/change times match. Changed files are verified again; failed checks are never cached as successful. `fetch(..., recheck=True)` forces verification. A new instance verifies independently. This is not a promise to recompute a cryptographic digest on every call or to protect against an adversary who can forge filesystem state.

Within one read, each flight's samples use one HDF5 handle and each source identity coordinate is loaded once. Initial verification has its own short-lived handle. All handles close on success and exceptions. A file change detected during reading invalidates the result. The implementation retains verification records, not file handles or measurement arrays, between calls. A bad existing cache file raises an error; it is not silently replaced.
