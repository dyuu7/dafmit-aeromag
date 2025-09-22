# Changelog

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
