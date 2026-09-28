# Maintenance

## Follow the responsibility boundaries

The public interface is `Dataset`, immutable `Selection`, the `FlightInfo` report, and standalone `to_xarray`. Keep scientific experiment choices outside the reader.

| Module | Responsibility |
| --- | --- |
| `dataset.py` | Validate public calls, coordinate catalog/file/reader operations, attach provenance |
| `selection.py`, `_validation.py` | Normalize constraints and ordered inputs once |
| `catalog_core.py` | Private release snapshot and detached offline metadata queries |
| `storage.py` | Download, byte verification, and instance-local verification records |
| `_hdf5.py` | Shared file structure and identity-value validation |
| `reader.py` | Actual sample discovery, explicit masks, schema planning, file resource lifetime |
| `conversion.py` | Convert a loaded frame without requiring dataset state |

The reader must not infer sample membership from `is_holdout`. Missing-field filling must not become corruption recovery. Do not introduce another public configuration layer for choices already expressed by `Selection` or `read` arguments.

## Update the catalog

The bundled catalog deliberately pins one Zenodo release. Rebuild it when deliberately adopting or reviewing source metadata:

```bash
uv run python scripts/update_catalog.py --record 12723700
uv run python scripts/update_catalog.py --check
```

This downloads the record and small readme archives, not HDF5 payloads. Review file identities, dates, units, source links, and segment annotations. `is_holdout` preserves an upstream note; it does not assert availability. The GitHub readme revision is pinned in `scripts/update_catalog.py`.

When Zenodo is temporarily unavailable, reuse the checked-in file identities with pinned GitHub readmes:

```bash
uv run python scripts/update_catalog.py --base-catalog src/dafmit_aeromag/catalog/v3.json
uv run python scripts/update_catalog.py --base-catalog src/dafmit_aeromag/catalog/v3.json --check
```

Both entry paths call the same catalog assembly code, so segment interpretation cannot drift between them. The fallback changes the metadata retrieval source; it does not discover new release files. Any change to the release or checksums requires the normal Zenodo path and review.

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

Ordinary tests create small real HDF5 files with matching test manifest hashes. They exercise public behavior, checksum reuse/invalidation, schema and coordinate corruption, batch order/empty results, resource cleanup, and xarray conversion. Catalog-generation tests compare both retrieval paths without a network dependency. CI covers Python 3.10–3.14.

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

Every documentation page has matching `.en.md` and `.zh.md` sources. Update both, run the parity check, and build with strict mode. When examples or contracts change, verify example code against appropriate fixtures or published files.

The weekly `upstream.yml` workflow follows the concept DOI and reports a newer release through a GitHub issue. It does not rewrite the catalog. A maintainer reviews the new release explicitly.

Before release, run tests, lint, format/type checks, documentation and distribution builds; review provenance/terms links and the changelog. Keep the version consistent in `pyproject.toml`, `__init__.py`, `CITATION.cff`, and the root entry in `uv.lock`. Creating a `vX.Y.Z` tag triggers the configured publish workflow, which creates the GitHub Release and publishes the built distributions through PyPI Trusted Publishing.
