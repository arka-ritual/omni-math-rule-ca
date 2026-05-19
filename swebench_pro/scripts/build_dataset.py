#!/usr/bin/env python3
"""Build the full SWE-bench Pro instance JSONL used for inference.

Produces `swebench_pro/data/swebench_pro_full.jsonl` with one line per
instance, each containing the minimal set of fields that
`run_mini_on_pro.py` needs:

    {
        "instance_id":       "<bare id, NO 'instance_' prefix>",
        "image_name":        "docker.io/<dockerhub_username>/sweap-images:<tag>",
        "problem_statement": "...",
    }

Source of truth: upstream's
`external/SWE-bench_Pro-os/helper_code/sweap_eval_full_v2.jsonl` (731
rows). That file's `image_name` field points at a private ECR URI, so
we replace it with the public Docker Hub image computed by upstream's
`helper_code/image_uri.py` (same logic the eval harness uses to pull
the test image).

Run `bash swebench_pro/scripts/setup_eval_repo.sh` first if
`external/SWE-bench_Pro-os/` is missing.

Usage:
    python swebench_pro/scripts/build_dataset.py
    python swebench_pro/scripts/build_dataset.py \
        --dockerhub-username jefzda \
        --output swebench_pro/data/swebench_pro_full.jsonl
"""
import argparse
import json
import sys
from pathlib import Path


def _load_image_uri_fn(upstream: Path):
    sys.path.insert(0, str(upstream))
    try:
        from helper_code.image_uri import get_dockerhub_image_uri  # type: ignore
    finally:
        sys.path.pop(0)
    return get_dockerhub_image_uri


def main():
    here = Path(__file__).resolve().parent
    swebench_pro = here.parent
    default_upstream = swebench_pro / "external/SWE-bench_Pro-os"
    default_out = swebench_pro / "data/swebench_pro_full.jsonl"

    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", default=str(default_upstream),
                    help="Path to cloned scaleapi/SWE-bench_Pro-os")
    ap.add_argument("--dockerhub-username", default="jefzda",
                    help="Docker Hub username serving the sweap-images:* tags "
                         "(default: jefzda — official SWE-bench Pro mirror)")
    ap.add_argument("--output", default=str(default_out),
                    help="Output JSONL path")
    args = ap.parse_args()

    upstream = Path(args.upstream)
    src = upstream / "helper_code/sweap_eval_full_v2.jsonl"
    if not src.exists():
        sys.exit(f"missing upstream file: {src}\n"
                 f"Run: bash swebench_pro/scripts/setup_eval_repo.sh")
    get_dockerhub_image_uri = _load_image_uri_fn(upstream)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    n_in = n_out = 0
    with src.open() as fin, out.open("w") as fout:
        for line in fin:
            n_in += 1
            item = json.loads(line)
            iid_prefixed = item["instance_id"]
            bare_iid = iid_prefixed.removeprefix("instance_")
            tag = get_dockerhub_image_uri(
                iid_prefixed, args.dockerhub_username, item.get("repo", "")
            )
            image_name = f"docker.io/{tag}"
            fout.write(json.dumps({
                "instance_id": bare_iid,
                "image_name": image_name,
                "problem_statement": item["problem_statement"],
            }) + "\n")
            n_out += 1

    print(f"Wrote {n_out}/{n_in} instances -> {out}")


if __name__ == "__main__":
    main()
