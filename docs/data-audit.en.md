# Audit of published files

This audit supports the 0.4 interface change. It examined the pinned Zenodo v3 record, both release readme archives and datasheets, and the actual Flt1004 (2020) and Flt2005 (2021) HDF5 files. The sample-level conclusions below concern **these two files**, not a claim that all 16 payloads were inspected.

## What the upstream release says

The [v3 record](https://zenodo.org/records/12723700) lists 16 HDF5 files, all named `Flt*_train.h5`, with no separate test/holdout HDF5 payload. Parsing the two release readme archives gives 175 documented segments, 19 marked as holdout. Those are documentation counts, not sample-availability counts.

The [2020 datasheet](https://zenodo.org/records/12723700/files/datasheet_sgl_2020_train.pdf?download=1) explains that the released data is a temporally partitioned subset. The [2021 datasheet](https://zenodo.org/records/12723700/files/datasheet_sgl_2021_train.pdf?download=1), page 2, says that Flt2005 and Flt2017 contain takeoff/transit portions while later portions are held out for testing. Its flight table reports 6361 samples for Flt2005.

Thus train/holdout is an upstream release and evaluation concept. The published payload is still a multichannel time series. Holdout does not mean low-quality or disposable data, and retaining an annotation cannot make unreleased samples available.

## Verified bytes and physical contents

Sizes and MD5 checksums match the pinned release manifest. A sample field here means a one-dimensional dataset with the same length as `tt`; scalar `N`, `dt`, and `info` are excluded.

| File | Bytes | MD5 | Samples | Physical sample fields | Observed `tt` range |
| --- | ---: | --- | ---: | ---: | --- |
| `Flt1004_train.h5` | 62722064 | `a17c1678407c02f260d7250b4e6c3a15` | 81408 | 96 | 44370.0–56891.0 |
| `Flt2005_train.h5` | 3235396 | `762e902bb3363508d5b947b7f4910eed` | 6361 | 61 | 54616.0–55252.0 |

Both declare `dt=0.1`. Neither inspected file contains a `split` dataset or HDF5 attributes assigning training/holdout roles. The 2020 field definitions include 99 names; Flt1004 lacks `year`, `doy`, and `mag_6_uc`. Normalized reads derive the first two from its date. They do not synthesize the missing magnetic measurement unless the caller explicitly requests missing-field filling.

## The missing segments and the boundary mistake

In Flt1004, readme holdout lines `4014.00` and `4013.00` are absent. Their documented intervals, 52982.8–53588.29 and 53774.43–54375.97 seconds, contain no samples. Actual `tt` jumps from 52862.1 directly to 54518.2. Other gaps also exist; a gap alone is not proof of a holdout partition.

All 6361 samples in Flt2005 belong to line `2004.00`, the takeoff/transit portion. The final sample has `tt=55252.0`, `line=2004.00`, and `mag_1_uc=53683.432`. The next documented segment, holdout line `2004.01`, starts at 55252.0. No samples with that line label occur in the file, nor do the later documented holdout lines.

Version 0.3 classified holdout using readme time intervals alone. It incorrectly assigned that last transit sample to holdout:

| Read | Flt1004 rows | Flt2005 rows |
| --- | ---: | ---: |
| 0.3 `split="all"` | 81408 | 6361 |
| 0.3 default `split="train"` | 81408 | 6360 |
| 0.3 `split="holdout"` | 0 (`NoDataError`) | 1 |
| 0.4 `Selection.all(...)` | 81408 | 6361 |

The single old “holdout” row was a boundary-classification error, not a usable evaluation set. An explicit 0.4 selection `tt=slice(54616, 55252)` still returns 6360 rows, correctly following the caller's half-open interval. Reading line `"2004.00"` returns all 6361.

## Reproduce the verification

`tests/test_integration.py` checks full-file sample counts and values against h5py, the boundary sample, absent documented lines, the 2020 gap and field differences, and real datetime conversion. Use verified local copies without network access:

```bash
MAGNAV_INTEGRATION=1 MAGNAV_DATA_DIR=/path/to/flight-files uv run pytest -m integration
```

The directory must contain the two original filenames above. Without `MAGNAV_DATA_DIR`, enabling integration tests downloads those files into a temporary directory and checks their pinned sizes and hashes. The source payloads are not committed to this repository.

The implementation keeps `is_holdout` and source links as documentation, and lets `read()` select actual samples using only explicit flight, line, and time constraints. This also avoids projecting one upstream evaluation design onto every downstream experiment.
