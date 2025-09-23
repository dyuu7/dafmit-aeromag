#!/usr/bin/env python3
"""Open or update an issue when the concept DOI points at a newer record."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any


def _request(
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    body: Any = None,
) -> Any:
    headers = {"User-Agent": "dafmit-aeromag-upstream-monitor"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


def _latest_record_id(concept_doi: str) -> int:
    request = urllib.request.Request(
        f"https://doi.org/{concept_doi}",
        headers={"User-Agent": "dafmit-aeromag-upstream-monitor"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        location = response.geturl()
    match = re.search(r"/records/(\d+)", location)
    if match is None:
        raise RuntimeError(
            f"could not resolve concept DOI to a Zenodo record: {location}"
        )
    return int(match.group(1))


def _catalog_metadata() -> dict[str, Any]:
    resource = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "dafmit_aeromag"
        / "catalog"
        / "v3.json"
    )
    return json.loads(resource.read_text(encoding="utf-8"))


def _issue_body(current: dict[str, Any], latest_id: int) -> str:
    return f"""A weekly check found a newer Zenodo record for the concept DOI.

- Current catalog: [{current["doi"]}](https://zenodo.org/records/{current["record_id"]})
- Latest record: [Zenodo record {latest_id}](https://zenodo.org/records/{latest_id})
- Concept DOI: [{current["concept_doi"]}](https://doi.org/{current["concept_doi"]})

Review the new record, its data-sharing terms, field schema, checksums, and
segment metadata. Do not edit `v3.json` automatically. Rebuild the catalog
with `scripts/update_catalog.py` only after a maintainer decides on a release
strategy.
"""


def main() -> int:
    current = _catalog_metadata()
    latest_id = _latest_record_id(current["concept_doi"])
    print(f"catalog record={current['record_id']} latest record={latest_id}")
    if latest_id == int(current["record_id"]):
        return 0

    token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repository:
        print("GITHUB_TOKEN/GITHUB_REPOSITORY unavailable; issue not created")
        return 1

    title = f"Upstream Zenodo release {latest_id} needs review"
    api = f"https://api.github.com/repos/{repository}/issues"
    open_issues = _request(f"{api}?state=open&per_page=100", token=token)
    body = _issue_body(current, latest_id)
    existing = next(
        (issue for issue in open_issues if issue.get("title") == title),
        None,
    )
    if existing:
        _request(existing["url"], method="PATCH", token=token, body={"body": body})
        print(f"updated issue #{existing['number']}")
    else:
        created = _request(
            api,
            method="POST",
            token=token,
            body={"title": title, "body": body},
        )
        print(f"created issue #{created['number']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
