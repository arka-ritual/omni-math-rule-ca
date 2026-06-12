#!/usr/bin/env python3
"""Build an out-of-distribution, non-agentic eval slice from Humanity's Last Exam.

Filters cais/hle to a category (default "Humanities/Social Science"), drops
image-based questions (the models here are run text-only), deterministically
samples n rows, and writes them in the inference row schema expected by
inference/inference_vllm.py + evaluation/math_eval_cautious.py
(`problem` = question, `answer` = ground truth).

Requires HF auth (the dataset is gated): `huggingface-cli login` first.

Usage:
  python scripts/build_hle_eval.py            # 100 Humanities/Social Science, text-only
  python scripts/build_hle_eval.py --n 100 --category "Humanities/Social Science"
"""
import argparse
import json
import os
import random

from datasets import load_dataset


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default="cais/hle")
    p.add_argument("--split", default="test")
    p.add_argument("--category", default="Humanities/Social Science")
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--include_images", action="store_true",
                   help="Keep image-based questions (default: drop them — text-only models).")
    p.add_argument("--out", default="data/hle/hle_humanities_ss_n100.jsonl")
    args = p.parse_args()

    ds = load_dataset(args.dataset, split=args.split)
    rows = [r for r in ds if r["category"] == args.category]
    if not args.include_images:
        rows = [r for r in rows if not r.get("image")]
    print(f"[hle] {args.category}: {len(rows)} eligible rows "
          f"(images {'kept' if args.include_images else 'dropped'})")

    random.Random(args.seed).shuffle(rows)
    rows = rows[:args.n]
    if len(rows) < args.n:
        print(f"[hle] WARNING: only {len(rows)} rows available (< n={args.n})")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for i, r in enumerate(rows):
            f.write(json.dumps({
                "idx": i,
                "hle_id": r["id"],
                "problem": r["question"],
                "answer": r["answer"],
                "answer_type": r["answer_type"],
                "raw_subject": r.get("raw_subject"),
                "category": r["category"],
            }, ensure_ascii=False) + "\n")

    n_mc = sum(1 for r in rows if r["answer_type"] == "multipleChoice")
    print(f"[hle] wrote {len(rows)} rows -> {args.out} "
          f"(multipleChoice={n_mc}, exactMatch={len(rows) - n_mc})")


if __name__ == "__main__":
    main()
