#!/usr/bin/env python3
"""Convert mini-swe-agent's preds.json into the patches JSON that
`swe_bench_pro_eval.py` expects.

Input:  <rundir>/preds.json
Output: <rundir>/eval/patches_for_eval.json

Notes
-----
* Empty patches are skipped (the eval would mark them False anyway; we record
  them in `<rundir>/eval/skipped_empty.txt` for auditing).
* The upstream eval index uses `instance_<id>`-prefixed instance ids
  everywhere (`run_scripts/instance_<id>/...`, `dockerfiles/.../instance_<id>/...`,
  `sweap_eval_full_v2.jsonl`). Mini-swe-agent's preds.json uses bare ids.
  By default we add the `instance_` prefix during conversion. Pass
  `--no-prefix` if your preds.json already uses prefixed ids.
"""
import argparse
import json
import sys
from pathlib import Path


def convert(rundir: Path, add_prefix: bool = True) -> Path:
    preds_path = rundir / "preds.json"
    if not preds_path.exists():
        sys.exit(f"missing: {preds_path}")
    out_dir = rundir / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "patches_for_eval.json"
    skipped_log = out_dir / "skipped_empty.txt"

    with preds_path.open() as f:
        preds = json.load(f)

    patches = []
    skipped: list[str] = []
    for iid, entry in preds.items():
        # Preserve the patch byte-for-byte. .strip() here would remove the
        # trailing \n that `git apply` requires; without it the patch is
        # rejected as "corrupt patch at line N" and the instance silently
        # scores false. Only strip for the empty-check.
        patch = entry.get("model_patch") or ""
        eval_iid = iid if (iid.startswith("instance_") or not add_prefix) else f"instance_{iid}"
        if not patch.strip():
            skipped.append(eval_iid)
            continue
        # Make sure the patch ends with exactly one newline — git apply also
        # rejects patches whose final hunk line lacks a trailing newline,
        # which can happen if the model's `cat patch.txt` captured a file
        # without a trailing newline.
        if not patch.endswith("\n"):
            patch = patch + "\n"
        patches.append({
            "instance_id": eval_iid,
            "model_patch": patch,
            "prefix": "mini",
        })

    with out_path.open("w") as f:
        json.dump(patches, f)
    skipped_log.write_text("\n".join(skipped))

    print(f"  rundir:       {rundir}")
    print(f"  preds total:  {len(preds)}")
    print(f"  with patch:   {len(patches)}")
    print(f"  skipped empty:{len(skipped)}")
    print(f"  wrote:        {out_path}")
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rundir", help="path to a single rundir containing preds.json")
    ap.add_argument(
        "--no-prefix",
        action="store_true",
        help="do not prepend 'instance_' to instance_ids during conversion",
    )
    args = ap.parse_args()
    convert(Path(args.rundir), add_prefix=not args.no_prefix)


if __name__ == "__main__":
    main()
