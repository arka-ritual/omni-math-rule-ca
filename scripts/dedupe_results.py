#!/usr/bin/env python3
"""Report and remove duplicate `idx` records from an inference results JSONL.

`inference/inference_api.py` appends as it goes and resumes by reading the
`idx` values already in the file. That is safe when runs are sequential, but if
a run is interrupted and a second one is started while the first is still
draining its in-flight requests, both write to the same file and the same
problem can land twice. The evaluators count lines, so duplicates silently
inflate `num_total` and double-weight those problems.

Default is a dry run — it tells you what it found and changes nothing. Pass
`--fix` to rewrite the file, keeping the FIRST record for each `idx` (the one
the resume logic considered "already done") and saving a `.bak` alongside.

Usage:
    python scripts/dedupe_results.py inference/results/**/foo.jsonl
    python scripts/dedupe_results.py --fix path1.jsonl path2.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys


def scan(path: str) -> tuple[list[str], dict, int]:
    """Return (kept_lines, duplicate_counts, malformed_count)."""
    kept: list[str] = []
    seen: set = set()
    dup_counts: dict = {}
    malformed = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            try:
                idx = json.loads(line)["idx"]
            except Exception:
                malformed += 1
                kept.append(line)  # keep — don't destroy data we can't parse
                continue
            if idx in seen:
                dup_counts[idx] = dup_counts.get(idx, 1) + 1
                continue
            seen.add(idx)
            kept.append(line)
    return kept, dup_counts, malformed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--fix", action="store_true",
                    help="Rewrite the file(s) keeping the first record per idx. "
                         "Without this, only reports.")
    args = ap.parse_args()

    any_dupes = False
    for path in args.paths:
        if not os.path.exists(path):
            print(f"{path}: MISSING", file=sys.stderr)
            continue
        kept, dups, malformed = scan(path)
        total = sum(dups.values()) - len(dups) + len(kept)
        if not dups and not malformed:
            print(f"{path}: clean ({len(kept)} records)")
            continue
        any_dupes = any_dupes or bool(dups)
        extra = sum(v - 1 for v in dups.values())
        print(f"{path}: {total} lines -> {len(kept)} unique "
              f"({extra} duplicate record(s) across {len(dups)} idx"
              f"{f', {malformed} malformed line(s) kept as-is' if malformed else ''})")
        if args.fix:
            shutil.copy2(path, path + ".bak")
            with open(path, "w", encoding="utf-8") as f:
                for line in kept:
                    f.write(line + "\n")
            print(f"  fixed; original saved to {path}.bak")

    if any_dupes and not args.fix:
        print("\nRe-run with --fix to rewrite.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
