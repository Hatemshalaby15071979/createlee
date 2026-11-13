#!/usr/bin/env python3
"""ME-15 guard: every agent-instruction file must carry the quarantine header.

Agent-directive files (prompts, constitutions) are *data, not instructions*. They
must contain the UNTRUSTED AGENT TEXT (ME-15) marker so an automated agent does
not treat their contents as commands to act on. This fails the build if a matching
file is missing the marker, so a new agent-instruction file cannot be introduced
without being explicitly quarantined.
"""
import glob
import sys

MARKER = "UNTRUSTED AGENT TEXT (ME-15)"

PATTERNS = [
    "opencode_next_step_kit/*.txt",
    "opencode_next_step_kit/**/*.txt",
    "Createlee_platform/Createlee/CREATELEE_CONSTITUTION.md",
]


def main() -> int:
    missing = []
    for pat in PATTERNS:
        for path in glob.glob(pat, recursive=True):
            try:
                text = open(path, encoding="utf-8").read()
            except OSError as exc:
                print(f"ERROR reading {path}: {exc}")
                return 2
            if MARKER not in text:
                missing.append(path)
    if missing:
        print("ME-15 FAIL: agent-instruction files missing the quarantine header:")
        for p in missing:
            print(f"  - {p}")
        return 1
    print("ME-15 OK: all agent-instruction files carry the UNTRUSTED AGENT TEXT (ME-15) header.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
