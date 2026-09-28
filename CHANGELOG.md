# Changelog

## 0.4.0

- Removed read-time `split` filtering. Reads preserve all actual samples matching explicit flight, line, and time constraints, including the last transit sample in Flt2005 (6361 total rather than 6360).
- Preserved upstream holdout annotations as `segments().is_holdout`, without inferring sample availability or data quality; removed `released` and `has_holdout` claims. Documented checksummed Flt1004/Flt2005 findings in a bilingual file audit.
- Separated offline field definitions from actual file inspection with `inspect(flight) -> FlightInfo`. Unified keyword-only catalog scopes, deduplicated `field_names()`, and made `field_groups()` return group summaries.
- Made columns explicit and accepted strings, Series/Index, arrays, and generators. Added identity-only reads and explicit `empty="allow"`; preserved batch order, duplicates, empty schemas, and per-selection row counts.
- Distinguished unknown, missing, and malformed fields, including real undocumented sample fields. Validated open time bounds, file structures, and coordinate values consistently in normalized and raw reads.
- Reused verification within a dataset instance while filesystem state matches, added `fetch(..., recheck=True)`, and shared file handles and coordinates within batches with deterministic cleanup.
- Made release metadata and catalog results detached copies, made dataset configuration read-only, and replaced `InvalidSelectionError` with `InvalidArgumentError`.
- Moved conversion to standalone `to_xarray(frame)` with real UTC datetime coordinates, preserved duplicate times, copied provenance, and attached units.
- Unified Zenodo and pinned-readme fallback catalog assembly. Expanded offline and real-file tests, API documentation, and migration guidance. This release intentionally provides no compatibility aliases.

## 0.3.0

- Added explicit `train`, `holdout`, and `all` split selection to `Dataset.read()` while keeping training data as the default.
- Added structured field groups, field notes, flight notes, sensor positions, and upstream source links to the release catalog.
- Pinned the upstream readme reference to a commit and documented Zenodo, upstream, and derived-catalog responsibilities.
- Added catalog discovery APIs for `field_groups()`, `field_names()`, and `sensors()`, plus documentation for the verified raw-file escape hatch.
- Added parser coverage and refreshed the bundled v3 metadata from the upstream 2020 and 2021 readmes.

## 0.2.0

- Renamed the project to `dafmit-aeromag` and replaced the stateful `sgl2020` helper with an explicit `Dataset` and `Selection` API.
- Added a checked-in Zenodo v3 catalog covering the 2020 and 2021 training flights, including field and segment metadata.
- Added verified lazy downloads, normalized/raw output modes, schema-aware missing-field handling, optional xarray conversion, tests, documentation, CI, and release workflows.
