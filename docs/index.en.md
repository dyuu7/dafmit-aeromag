# DAF-MIT AeroMag

`dafmit-aeromag` provides a small, explicit Python interface to the DAF-MIT AIA open flight dataset for aircraft magnetic interference compensation and MagNav research. It covers the published 2020 and 2021 flight collections from Zenodo release v3 while keeping large HDF5 files outside the package.

This is an independent project and is not affiliated with or endorsed by the dataset authors or their institutions.

The public surface is deliberately compact:

```python
from dafmit_aeromag import Dataset, Selection

data = Dataset()
frame = data.read(
    Selection(flight=2005, lines="2004.00"),
    columns=["mag_1_uc", "ins_lat", "ins_lon"],
)
```

Start with the [quickstart](quickstart.md), then read the [data model](data-model.md) for the release and schema details.

Reads use explicit flight, line, and time constraints. Upstream holdout annotations remain inspectable metadata; they never silently remove rows. See the [file audit](data-audit.md) for the evidence and the [migration guide](migration.md) for changes in 0.4.
