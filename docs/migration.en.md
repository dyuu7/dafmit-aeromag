# Migration to 0.4

Version 0.4 deliberately breaks the ambiguous 0.3 interface. There are no compatibility aliases. The most consequential change is sample selection: reads now return the samples present in the file that match your explicit constraints, with no automatic training/holdout mask.

| Previous usage or assumption | 0.4 replacement |
| --- | --- |
| `read(..., split="all")` | Remove `split`; this is now the ordinary source view |
| Default reads or `split="train"` | Remove `split` and review sample counts; define experimental subsets explicitly |
| `read(..., split="holdout")` | No automatic replacement; inspect documentation and actual coverage, then supply explicit selections |
| `segments(..., split=...)` | `segments(...)`; inspect/filter `is_holdout` on the returned table |
| `split`, `released`, `has_holdout` metadata | `is_holdout` on segment rows only; it is an annotation, not availability |
| `fields(flight=...)` with an `available` column | Collection definitions only; use `inspect(flight).fields` for actual fields |
| `field_names("ins", flight=2005)` | `field_names(group="ins", flight=2005)` |
| `field_groups()` as an expanded field table | `field_groups()` gives group/description/count; use `fields(group=...)` for members |
| `data.catalog` | Public `metadata` and catalog query methods; returned values are detached |
| `data.to_xarray(frame)` | `from dafmit_aeromag import to_xarray; to_xarray(frame)` |
| `InvalidSelectionError` | `InvalidArgumentError`, also a `ValueError` |
| Silently skipped empty members of a batch | Default `NoDataError`; opt into `empty="allow"` |
| Assigning dataset configuration after construction | Construct another `Dataset` with the desired settings |

## Review experimental assumptions

Flt2005 now returns 6361 samples rather than the old default 6360. The additional row is the real last transit sample, incorrectly filtered by the old implementation. It is not newly published test data. The [audit](data-audit.md) explains the exact boundary.

Do not replace `split="holdout"` with an assumed collection of usable rows. The readme can describe intervals absent from the public file. `is_holdout` is neither a bad-data flag nor proof that training data exists when false. For reproducible evaluation, define and document the flight/line/time subsets your experiment actually uses.

## Predictable discovery and reads

```python
from dafmit_aeromag import Dataset, Selection, to_xarray

data = Dataset()
# Offline documentation; only 2021 definitions are returned.
names = data.field_names(flight=2005, group="scalar_magnetometer")
# Physical presence requires opening a verified file.
actual_fields = data.inspect(2005).fields
frame = data.read(Selection.all(2005), columns=names, missing="fill")
array = to_xarray(frame)
```

`columns` is required, including for all-field reads (`columns="all"`). A single string now means one field. `columns=[]` means the six normalized identity columns; `raw=True` requires at least one physical field. Series, Index, one-dimensional arrays, and generators are accepted directly. Sets and mappings are rejected. Both open and closed time bounds are validated when constructing a selection.

`missing="fill"` only handles absence. It does not accept unknown names, invalid shapes, or corrupt coordinates. For intentionally empty queries use `empty="allow"`; inspect `frame.attrs["selections"]` for every query's row count.

Reusing a `Dataset` reuses successful file verification while filesystem state is unchanged. Use `fetch(..., recheck=True)` for an explicit full recheck. xarray time is now `datetime64[ns]` rather than an object array; `sample` remains the dimension to preserve repeated times.

## Earlier `sgl2020` users

The distribution is `dafmit-aeromag` and the import namespace is `dafmit_aeromag`. The old stateful builder is not supported. Replace chains such as `Sgl2020().line(...).source(...).take()` with explicit `Dataset.read(Selection(flight, lines=...), columns=...)`. Supply the file's flight identifier separately from its line labels. See the [quickstart](quickstart.md) for a complete workflow.
