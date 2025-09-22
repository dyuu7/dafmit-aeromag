# Migration from `sgl2020`

Version 0.2 is a direct break and uses the new distribution name `dafmit-aeromag` with the import namespace `dafmit_aeromag`. The old `sgl2020` package and its stateful query builder are not compatibility aliases.

| Older pattern | New pattern |
| --- | --- |
| `from sgl2020 import Sgl2020` | `from dafmit_aeromag import Dataset, Selection` |
| `Sgl2020().line("1002.01").source(...).take()` | `Dataset().read(Selection(1002, lines="1002.01"), columns=[...])` |
| Hand-maintained 2020 descriptions | `Dataset().flights()`, `.fields()`, and `.segments()` |
| Implicit cache and moving DOI target | Fixed `v3` manifest plus configurable `data_dir` |

The new API makes flight scope explicit, supports 2021 files, and exposes normalized and raw output modes. Existing downstream code should migrate its imports and make its selected columns explicit.
