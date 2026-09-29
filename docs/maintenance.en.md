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
uv sync --locked
uv run --no-sync pytest --cov --cov-report=term-missing
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pyright
uv run --no-sync python scripts/check_versions.py
uv run --no-sync python scripts/check_i18n.py
uv run --no-sync mkdocs build --strict
uv run --no-sync python -m build
```

Ordinary tests create small real HDF5 files with matching test manifest hashes. They exercise public behavior, checksum reuse/invalidation, schema and coordinate corruption, batch order/empty results, and resource cleanup. Catalog-generation tests use synthetic release metadata and readme archives without a network dependency. CI tests Python 3.10–3.14 and collects coverage on Python 3.13. Version consistency, static checks, bilingual page checks, and documentation and distribution builds run once in a separate job. Workflows use `uv sync --locked` to reject an outdated lockfile. The publish workflow reuses this same CI workflow to validate the tagged commit and build its distributions.

## Test the published payloads

```bash
MAGNAV_INTEGRATION=1 uv run pytest -m integration
```

This verifies Flt1004 and Flt2005 from both collections. To reuse downloaded original files and prohibit network access:

```bash
MAGNAV_INTEGRATION=1 MAGNAV_DATA_DIR=/path/to/flight-files uv run pytest -m integration
```

See the [file audit](data-audit.md) for pinned sizes, checksums, expected counts, and the boundary regression. An unchanged source file can be reused; do not modify fixtures to conceal a real upstream mismatch. The Data integration workflow provides a manual `workflow_dispatch` entry point, separate from ordinary CI. Run it on the relevant branch or tag after changes to the reader, storage layer, or catalog, and before releasing. It has no scheduled trigger.

## Documentation and releases

Documentation describes the current interface and usage. The file audit preserves evidence and corrections that affect result interpretation. Every documentation page has matching `.en.md` and `.zh.md` sources. Update both, run the parity check, and build with strict mode. When examples or contracts change, verify example code against appropriate fixtures or published files.

Before release, run tests, lint, format/type checks, documentation and distribution builds; review provenance/terms links. Set the package version in `pyproject.toml`, update `CITATION.cff` to match, and run `uv lock` to refresh the lockfile. Runtime `__version__` comes from the installed package metadata, including editable installs created by `uv sync`. Ordinary CI checks the citation version against that metadata after syncing the project.

Creating a `vX.Y.Z` tag triggers the publish workflow, which runs the complete CI workflow on that commit and additionally checks the tag against the package version. Run `uv run python scripts/check_versions.py --tag vX.Y.Z` locally to check a proposed tag. After validation succeeds, the workflow publishes those same build artifacts through PyPI Trusted Publishing, then creates a GitHub Release with the distributions attached. Each tag creates one Release; existing Releases and their assets are not overwritten. Add a brief note about changes affecting usage or results to the corresponding GitHub Release when needed.
