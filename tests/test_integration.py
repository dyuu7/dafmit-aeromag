from __future__ import annotations

import os

import pytest

from dafmit_aeromag import Dataset, Selection


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("MAGNAV_INTEGRATION") != "1",
    reason="set MAGNAV_INTEGRATION=1 to download the real Flt2005 file",
)
def test_smallest_zenodo_flight(tmp_path) -> None:
    dataset = Dataset(data_dir=tmp_path, progress=False)
    frame = dataset.read(
        Selection(2005, lines="2004.00"),
        columns=["mag_1_uc", "ins_lat", "ins_lon"],
        split="train",
    )

    # The source includes a sample exactly at the documented holdout boundary;
    # the public interval convention is [start, stop).
    assert len(frame) == 6360
    assert frame["flight"].unique().tolist() == [2005]
    assert frame["line"].unique().tolist() == ["2004.00"]
