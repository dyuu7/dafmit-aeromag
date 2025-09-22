# Maintenance

## Updating the catalog

The checked-in catalog is deliberately fixed to a Zenodo record. Rebuild it only after reviewing the upstream release and its terms:

```bash
uv run python scripts/update_catalog.py --record 12723700
uv run python scripts/update_catalog.py --check
```

The script parses the Zenodo API response and the release readme archives. It does not download HDF5 data. Review the resulting diff for file URLs, checksums, field schema changes, and segment splits before merging. The upstream readme revision is pinned in `scripts/update_catalog.py`; update it deliberately when adopting a new metadata reference.

If the Zenodo API is temporarily unavailable, refresh the structured metadata from the checked-in file manifest and the upstream GitHub readmes:

```bash
uv run python scripts/update_catalog.py --base-catalog src/dafmit_aeromag/catalog/v3.json
uv run python scripts/update_catalog.py --base-catalog src/dafmit_aeromag/catalog/v3.json --check
```

This fallback does not discover new Zenodo files; use the normal record-based command when changing the release or file manifest. It also intentionally uses the pinned upstream revision rather than the mutable `master` branch.

## Documentation translations

Every page under `docs/` has an English `.en.md` source and a matching Chinese `.zh.md` source. Keep the two files aligned when adding or changing a page, and run the parity check before building the site:

```bash
uv run python scripts/check_i18n.py
```

## Upstream monitoring

The weekly `upstream.yml` workflow follows the concept DOI and opens or updates a GitHub issue when a newer Zenodo record appears. It does not modify the manifest automatically. A maintainer must inspect the release and make a deliberate catalog update.

## Release checklist

1. Run the full test, lint, type-check, documentation, and package-build jobs.
2. Review provenance and data-license links.
3. Update the catalog and changelog notes if the release intentionally changes data coverage.
4. Create a `vX.Y.Z` tag and publish through the trusted PyPI workflow.
