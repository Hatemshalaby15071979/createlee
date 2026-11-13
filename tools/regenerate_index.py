#!/usr/bin/env python3
"""Regenerate a delivery INDEX.csv from the files that actually exist.

The index must describe reality: every row is a file that is present, with its
real size and SHA-256. Rows for files that were never delivered (for example an
``evidence/`` folder that was an input to a build, not an output) are dropped.

Usage:
    python tools/regenerate_index.py <library_dir> [--origin-prefix PREFIX]

The column layout matches Createlee_platform/Createlee/library.py so the file
stays readable by the same consumers.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

COLUMNS = ["relative_path", "kind", "rows", "columns", "size_bytes", "sha256",
           "origin", "generated_at_iso8601"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_shape(path: Path) -> tuple[int | str, int | str]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
            rows = sum(1 for _ in reader)
        return rows, len(header)
    except (OSError, UnicodeDecodeError, csv.Error):
        return "", ""


def origin_for(relative: str) -> str:
    if relative.startswith("uploaded/"):
        return "USER-REAL"
    if relative.startswith("evidence/"):
        return "simulated (Signoff fixture)"
    if relative.startswith("systems/"):
        return "simulated"
    return "simulated / derived"


def generated_at(root: Path) -> str:
    manifest = root / "LIBRARY_MANIFEST.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        stamp = data.get("generated_at_iso8601")
        if isinstance(stamp, str) and stamp:
            return stamp
    except (OSError, ValueError):
        pass
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path)
    args = parser.parse_args()
    root = args.library.resolve()
    if not root.is_dir():
        parser.error(f"{root} is not a directory")

    stamp = generated_at(root)
    index_path = root / "INDEX.csv"
    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path == index_path:
            continue
        relative = path.relative_to(root).as_posix()
        row_count, column_count = ("", "")
        if path.suffix.lower() == ".csv":
            row_count, column_count = csv_shape(path)
        rows.append([relative, path.suffix.lower().lstrip("."), row_count, column_count,
                     path.stat().st_size, sha256(path), origin_for(relative), stamp])

    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMNS)
        writer.writerows(rows)

    print(f"wrote {index_path} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
