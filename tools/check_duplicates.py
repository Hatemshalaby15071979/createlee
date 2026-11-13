#!/usr/bin/env python3
"""Fail CI when the same file content is committed twice by accident.

Some duplication is deliberate:

* ``Createlee_platform/Createlee/handoff/**`` — each client pack must be
  shippable on its own, so it carries its own copy of the inputs.
* ``uploads/`` and ``system_library/uploaded/`` — the same six real uploads are
  ingested into each library copy.

Everything else should exist once. A group is acceptable when at most ONE
member sits outside the allow-list: that is the canonical copy. A second
outside member means a stray duplicate was committed and the check fails.

Usage:
    python tools/check_duplicates.py [repo_root]
"""
from __future__ import annotations

import collections
import hashlib
import subprocess
import sys
from pathlib import Path

ALLOWED_PREFIXES = (
    "Createlee_platform/Createlee/handoff/",
    # Delivered mirror of the app's system library; the app copy is canonical.
    "Createlee_system_library/",
    "Createlee_platform/Createlee/uploads/",
    "Createlee_platform/Createlee/system_library/uploaded/",
    "Createlee_system_library/uploaded/",
)


def tracked_files(root: Path) -> list[str]:
    result = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                            check=True, capture_output=True)
    return [p.decode("utf-8", "surrogateescape")
            for p in result.stdout.split(b"\0") if p]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    groups: dict[str, list[str]] = collections.defaultdict(list)
    for relative in tracked_files(root):
        path = root / relative
        if path.is_file():
            groups[digest(path)].append(relative)

    duplicates = {h: sorted(paths) for h, paths in groups.items() if len(paths) > 1}
    unexpected = {
        h: paths for h, paths in duplicates.items()
        if len([p for p in paths if not p.startswith(ALLOWED_PREFIXES)]) > 1
    }

    print(f"{len(groups)} distinct files; {len(duplicates)} duplicate group(s), "
          f"{len(unexpected)} unexpected.")
    for digest_value, paths in duplicates.items():
        marker = "FAIL" if digest_value in unexpected else "ok  "
        print(f"  {marker} {len(paths)}x {paths[0]}")
        for path in paths[1:]:
            print(f"          {path}")

    if unexpected:
        print("\nUnexpected byte-identical copies. Keep one canonical file, or add "
              "the directory to ALLOWED_PREFIXES with a reason.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
