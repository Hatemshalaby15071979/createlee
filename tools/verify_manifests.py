#!/usr/bin/env python3
"""Verify every committed manifest against the files it claims to describe.

Two failure modes are caught:

* an ``INDEX.csv`` that is not CSV at all (the root manifest shipped as an XLSX
  workbook for months, so every automated reader silently saw garbage), and
* a row whose ``sha256``/``size_bytes`` does not match the file on disk, or
  whose file is missing.

Usage:
    python tools/verify_manifests.py [repo_root]

Exit code 1 on any failure, 0 when every manifest is honest.
"""
from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

XLSX_MAGIC = b"PK\x03\x04"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_index(index: Path) -> list[str]:
    problems: list[str] = []
    raw = index.read_bytes()
    if raw.startswith(XLSX_MAGIC):
        return [f"{index}: is an XLSX workbook, not CSV"]
    if b"\x00" in raw[:1024]:
        return [f"{index}: looks binary, not CSV"]
    try:
        with index.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        return [f"{index}: cannot be parsed as CSV ({exc})"]

    if not rows:
        return [f"{index}: no data rows"]

    for number, row in enumerate(rows, start=2):
        relative = row.get("relative_path") or row.get("filename")
        if not relative:
            problems.append(f"{index}:{number}: no relative_path/filename column")
            continue
        target = index.parent / relative
        if not target.is_file():
            problems.append(f"{index}:{number}: missing file {relative}")
            continue
        expected_hash = (row.get("sha256") or "").strip().lower()
        if expected_hash:
            actual = sha256(target)
            if actual != expected_hash:
                problems.append(
                    f"{index}:{number}: sha256 mismatch for {relative} "
                    f"(expected {expected_hash[:12]}, actual {actual[:12]})"
                )
        expected_size = (row.get("size_bytes") or "").strip()
        if expected_size.isdigit() and int(expected_size) != target.stat().st_size:
            problems.append(
                f"{index}:{number}: size mismatch for {relative} "
                f"(expected {expected_size}, actual {target.stat().st_size})"
            )
    return problems


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    indexes = sorted(p for p in root.rglob("INDEX.csv")
                     if ".git" not in p.parts and "node_modules" not in p.parts)
    if not indexes:
        print("no INDEX.csv files found", file=sys.stderr)
        return 1

    problems: list[str] = []
    for index in indexes:
        found = verify_index(index)
        status = "OK" if not found else f"{len(found)} problem(s)"
        print(f"{index.relative_to(root)}: {status}")
        problems.extend(found)

    if problems:
        print("\nManifest problems:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"\nAll {len(indexes)} manifests verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
