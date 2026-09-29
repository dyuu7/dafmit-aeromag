from __future__ import annotations

import argparse
import re
from importlib.metadata import version
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check package and citation versions.")
    parser.add_argument("--tag", default="", help="Also check a vX.Y.Z release tag.")
    args = parser.parse_args()

    package_version = version("dafmit-aeromag")
    citation_version = str(
        yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))["version"]
    )
    if citation_version != package_version:
        print(
            f"CITATION.cff: version {citation_version!r} "
            f"does not match package version {package_version!r}"
        )
        return 1

    if args.tag:
        if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", args.tag):
            print(f"Expected a vX.Y.Z release tag, got {args.tag!r}")
            return 1
        if args.tag != f"v{package_version}":
            print(
                f"Release tag {args.tag!r} does not match version {package_version!r}"
            )
            return 1

    print(f"Checked package and citation versions: {package_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
