"""Repository security checks used by CI and the local test suite."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Iterable


def forbidden_tracked_env_paths(paths: Iterable[str]) -> list[str]:
    """Return tracked dotenv paths, allowing only the documented example file."""
    forbidden = []
    for raw_path in paths:
        path = PurePosixPath(raw_path)
        name = path.name.lower()
        if (name == ".env" or (name.startswith(".env.") and name != ".env.example")):
            forbidden.append(path.as_posix())
    return sorted(forbidden)


def tracked_ignored_paths(repository_root: Path) -> list[str] | None:
    """Return tracked paths matched by ignore rules, or None if inspection failed."""
    result = subprocess.run(
        ["git", "-C", str(repository_root), "ls-files", "-ci", "--exclude-standard", "-z"],
        check=False,
        capture_output=True,
    )
    if result.returncode:
        return None
    paths = [
        item.decode("utf-8", errors="surrogateescape")
        for item in result.stdout.split(b"\0")
        if item
    ]
    return sorted(paths)


def main() -> int:
    repository_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["git", "-C", str(repository_root), "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if result.returncode:
        print("Unable to inspect tracked paths; rejecting the build.", file=sys.stderr)
        return 2

    tracked_paths = [
        item.decode("utf-8", errors="surrogateescape")
        for item in result.stdout.split(b"\0")
        if item
    ]
    forbidden = forbidden_tracked_env_paths(tracked_paths)
    if forbidden:
        print("Tracked environment files are not allowed:")
        for path in forbidden:
            print(f"  {path}")
        return 1

    ignored = tracked_ignored_paths(repository_root)
    if ignored is None:
        print("Unable to reconcile tracked paths with ignore rules; rejecting the build.", file=sys.stderr)
        return 2
    if ignored:
        print("Tracked files matched by .gitignore are not allowed:")
        for path in ignored:
            print(f"  {path}")
        return 1

    print("No tracked environment files or ignored paths found (.env.example is allowed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
