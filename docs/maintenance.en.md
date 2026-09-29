# Maintenance

## Follow the responsibility boundaries

The public interface is `Dataset`, immutable `Selection`, and the `FlightInfo` report. Reads return pandas `DataFrame` objects. Keep scientific experiment choices and downstream format conversions outside the reader.

| Module | Responsibility |
| --- | --- |
| `dataset.py` | Validate public calls, coordinate catalog/file/reader operations, attach provenance |
| `selection.py`, `_validation.py` | Normalize constraints and ordered inputs once |
| `catalog_core.py` | Private release snapshot and detached offline metadata queries |
| `storage.py` | Download, byte verification, and instance-local verification records |
| `_hdf5.py` | Shared file structure and identity-value validation |
| `reader.py` | Actual sample discovery, explicit masks, schema planning, file resource lifetime |

The reader must not infer sample membership from `is_holdout`. Missing-field filling must not become corruption recovery. Do not introduce another public configuration layer for choices already expressed by `Selection` or `read` arguments.

## Update the catalog

The bundled catalog and generation script are fixed to Zenodo v3, record `12723700`. Rebuild the catalog when reviewing source metadata or changing its parsing rules:

```bash
uv run python scripts/update_catalog.py
uv run python scripts/update_catalog.py --check
```

This downloads the record and small readme archives, not HDF5 payloads. Review file identities, dates, units, source links, and segment annotations. `is_holdout` preserves an upstream note; it does not assert availability. The GitHub readme revision is pinned in `scripts/update_catalog.py`.

Use `--output /path/to/catalog.json` to write a separate file for comparison; `--check` compares the generated content with the output file without writing it. If Zenodo is temporarily unavailable, rerun the command later. Adopting another data release is a manual project update that includes the generator, bundled catalog, tests, and documentation.

## Test without downloading data

```bash
uv sync --frozen
uv run pytest --cov --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python scripts/check_i18n.py
uv run mkdocs build --strict
uv run python -m build
```

Ordinary tests create small real HDF5 files with matching test manifest hashes. They exercise public behavior, checksum reuse/invalidation, schema and coordinate corruption, batch order/empty results, and resource cleanup. Catalog-generation tests use synthetic release metadata and readme archives without a network dependency. CI covers Python 3.10–3.14.

## Test the published payloads

```bash
MAGNAV_INTEGRATION=1 uv run pytest -m integration
```

This verifies Flt1004 and Flt2005 from both collections. To reuse downloaded original files and prohibit network access:

```bash
MAGNAV_INTEGRATION=1 MAGNAV_DATA_DIR=/path/to/flight-files uv run pytest -m integration
```

See the [file audit](data-audit.md) for pinned sizes, checksums, expected counts, and the boundary regression. An unchanged source file can be reused; do not modify fixtures to conceal a real upstream mismatch. The scheduled integration workflow runs these tests separately from ordinary CI.

## Documentation and releases

Documentation describes the current interface and usage. The file audit preserves evidence and corrections that affect result interpretation. Every documentation page has matching `.en.md` and `.zh.md` sources. Update both, run the parity check, and build with strict mode. When examples or contracts change, verify example code against appropriate fixtures or published files.

Before release, run tests, lint, format/type checks, documentation and distribution builds; review provenance/terms links. Keep the version consistent in `pyproject.toml`, `__init__.py`, `CITATION.cff`, and the root entry in `uv.lock`. Creating a `vX.Y.Z` tag triggers the configured publish workflow, which creates the GitHub Release and publishes the built distributions through PyPI Trusted Publishing. Add a brief note about changes affecting usage or results to the corresponding GitHub Release when needed.
