# Data Model

## Releases and files

The package ships a fixed `v3` catalog for Zenodo record [`10.5281/zenodo.12723700`](https://doi.org/10.5281/zenodo.12723700). Each flight row records its collection, date, standard HDF5 filename, byte size, MD5 checksum, sample interval, flight notes, and the upstream readme URL.

HDF5 files are downloaded lazily into `Dataset.data_dir`. Existing files are checked for size, MD5, and HDF5 readability before use. A corrupt local file raises `DataIntegrityError` instead of being silently consumed.

## Selections

`Selection` is immutable and flight-scoped:

```python
Selection(flight=2017, lines=["2005.20", "2005.21"])
Selection(flight=1002, tt=slice(45100, 45200))
Selection(flight=1002, time=slice("2020-06-20T12:31:40Z", "2020-06-20T12:32:00Z"))
```

Line strings are canonicalized to two decimal places. Wildcards, ranges, and numeric floats are rejected so that a query cannot accidentally cross flight boundaries. `time` and `tt` are mutually exclusive. Both use left-closed/right-open bounds.

The catalog keeps segment ordinals separate from line labels. A line can be reused within a flight, and a line label can refer to a different survey flight, so the readme's flight file and time interval remain authoritative.

## Output modes

Normalized output has this identity prefix:

| Column | Meaning |
| --- | --- |
| `flight` | File/flight identifier |
| `line` | Canonical two-decimal line label |
| `year` | UTC calendar year |
| `doy` | UTC day of year |
| `tt` | Native seconds past midnight |
| `time` | UTC timestamp derived from identity and `tt` |

`raw=True` returns only the requested one-dimensional source datasets. Scalar metadata such as `N`, `dt`, and `info` is never presented as sample data.

The `split` argument controls how catalogued intervals are exposed:

| `split` | Behavior |
| --- | --- |
| `"train"` | Default. Exclude intervals marked `holdout`. |
| `"holdout"` | Return only intervals marked `holdout`. |
| `"all"` | Do not apply the catalog split mask. |

This keeps holdout samples out of the default training-data path while allowing evaluation workflows to request them explicitly. Use `Dataset.segments()` to inspect documented coverage before reading.

The 2020 and 2021 collections do not have identical field sets. Explicit columns fail fast by default; `missing="fill"` creates `NaN` values for fields not present in a selected file. `columns="all"` uses the physical sample-field union after files are opened, so a multi-flight read can still use `missing="fill"` when schema gaps are intentional.

## Field metadata and groups

`Dataset.fields()` exposes the original field name, units, description, collection, field-specific notes, and upstream source URL. `Dataset.field_groups()` adds a stable convenience grouping such as `navigation`, `scalar_magnetometer`, `fluxgate`, `ins`, `current`, and `voltage`; `Dataset.field_names()` returns the original HDF5 names for one group. These groups are for discovery only and do not replace the upstream field definitions.

`Dataset.sensors()` exposes the documented magnetometer and fluxgate positions relative to the front seat rail. The catalog links each row to the corresponding upstream field readme. For the complete source semantics, consult the [pinned MagNav.jl readmes](https://github.com/MIT-AI-Accelerator/MagNav.jl/tree/b79a9ceed6009878f47c72938718f96ce067d803/readmes), including the [2020 field definition](https://github.com/MIT-AI-Accelerator/MagNav.jl/blob/b79a9ceed6009878f47c72938718f96ce067d803/readmes/sgl_2020_fields_readme.txt) and [2021 field definition](https://github.com/MIT-AI-Accelerator/MagNav.jl/blob/b79a9ceed6009878f47c72938718f96ce067d803/readmes/sgl_2021_fields_readme.txt).

`Dataset.fetch()` is the raw-data escape hatch: it downloads and verifies the requested HDF5 file and returns its local path. The package does not copy the HDF5 files or flatten their complete source documentation into a second manual schema.
