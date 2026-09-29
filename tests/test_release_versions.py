from __future__ import annotations

import sys

import pytest
from scripts import check_versions


@pytest.mark.parametrize(
    ("citation", "tag", "exit_code", "message"),
    [
        ("1.2.3", None, 0, "Checked package and citation versions"),
        ("1.2.3", "", 0, "Checked package and citation versions"),
        ("1.2.3", "v1.2.3", 0, "Checked package and citation versions"),
        ("1.2.2", None, 1, "CITATION.cff: version '1.2.2'"),
        ("1.2.3", "v1.2.4", 1, "Release tag 'v1.2.4' does not match"),
        ("1.2.3", "1.2.3", 1, "Expected a vX.Y.Z release tag"),
        ("1.2.3", "v1.2.3rc1", 1, "Expected a vX.Y.Z release tag"),
    ],
)
def test_release_version_checks(
    tmp_path, monkeypatch, capsys, citation, tag, exit_code, message
):
    (tmp_path / "CITATION.cff").write_text(f'version: "{citation}"\n')
    monkeypatch.setattr(check_versions, "ROOT", tmp_path)
    monkeypatch.setattr(check_versions, "version", lambda name: "1.2.3")
    argv = ["check_versions.py"]
    if tag is not None:
        argv.extend(["--tag", tag])
    monkeypatch.setattr(sys, "argv", argv)

    assert check_versions.main() == exit_code
    assert message in capsys.readouterr().out
