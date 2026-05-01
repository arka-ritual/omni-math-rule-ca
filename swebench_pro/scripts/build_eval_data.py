#!/usr/bin/env python3
"""Build a per-rundir normalized eval JSONL from upstream's
`helper_code/sweap_eval_full_v2.jsonl`.

The upstream JSONL has 731 instances and uses uppercase keys for
`FAIL_TO_PASS` / `PASS_TO_PASS`. The eval script (`swe_bench_pro_eval.py`)
expects lowercase keys and reads them as JSON-encoded strings via `eval()`,
so list-typed values must be re-serialized as JSON strings.

This script:
  1. Reads instance ids from <rundir>/preds.json (or, with --gold, from --ids).
  2. Selects matching rows in the upstream JSONL (matching either the bare id
     or the `instance_`-prefixed id).
  3. Renames FAIL_TO_PASS -> fail_to_pass, PASS_TO_PASS -> pass_to_pass.
  4. Re-serializes list values as JSON strings.
  5. Writes <rundir>/eval/eval_data.jsonl.

Usage:
    python build_eval_data.py <rundir> --upstream <SWE-bench_Pro-os>
    python build_eval_data.py --ids ids.txt --upstream <SWE-bench_Pro-os> --output eval_data.jsonl
"""
import argparse
import json
import sys
from pathlib import Path


def load_instance_ids(rundir: Path | None, ids_file: Path | None) -> set[str]:
    if ids_file is not None:
        return {ln.strip() for ln in ids_file.read_text().splitlines() if ln.strip()}
    assert rundir is not None
    preds = json.loads((rundir / "preds.json").read_text())
    return set(preds.keys())


def normalize_row(item: dict) -> dict:
    renames = {"FAIL_TO_PASS": "fail_to_pass", "PASS_TO_PASS": "pass_to_pass"}
    for old, new in renames.items():
        if old in item and new not in item:
            item[new] = item.pop(old)
    for field in ("fail_to_pass", "pass_to_pass"):
        if field in item and isinstance(item[field], list):
            item[field] = json.dumps(item[field])
    return item


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rundir", nargs="?", help="rundir containing preds.json")
    ap.add_argument("--ids", help="path to a newline-separated list of instance ids")
    ap.add_argument(
        "--upstream",
        required=True,
        help="path to the cloned SWE-bench_Pro-os repo",
    )
    ap.add_argument(
        "--output",
        help="output JSONL path (default: <rundir>/eval/eval_data.jsonl)",
    )
    args = ap.parse_args()

    if args.rundir is None and args.ids is None:
        sys.exit("Pass either <rundir> or --ids")

    rundir = Path(args.rundir) if args.rundir else None
    ids_file = Path(args.ids) if args.ids else None
    wanted = load_instance_ids(rundir, ids_file)
    # Match by bare id and prefixed id, both directions.
    wanted_bare = {w.removeprefix("instance_") for w in wanted}

    src = Path(args.upstream) / "helper_code/sweap_eval_full_v2.jsonl"
    if not src.exists():
        sys.exit(f"missing upstream eval data: {src}")

    if args.output:
        out = Path(args.output)
    else:
        assert rundir is not None
        out = rundir / "eval/eval_data.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    matched_ids: set[str] = set()
    with src.open() as fin, out.open("w") as fout:
        for line in fin:
            item = json.loads(line)
            iid = item.get("instance_id", "")
            bare = iid.removeprefix("instance_")
            if iid not in wanted and bare not in wanted_bare:
                continue
            fout.write(json.dumps(normalize_row(item)) + "\n")
            matched_ids.add(bare)

    missing = wanted_bare - matched_ids
    print(f"matched {len(matched_ids)}/{len(wanted_bare)} instances -> {out}")
    if missing:
        print(f"  WARNING: {len(missing)} ids not found in upstream eval data:")
        for mid in sorted(missing)[:5]:
            print(f"    - {mid}")


if __name__ == "__main__":
    main()
