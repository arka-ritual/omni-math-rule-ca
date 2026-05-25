#!/usr/bin/env python3
"""Random train/validate/eval split of omni_math_rule.jsonl.

Default sizes: 2000 train / 221 validate / 600 eval (sums to 2821 = full dataset).
Splits are deterministic given --seed.
"""
import argparse
import json
import os
import random


def read_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--omni", default="omni_math_rule.jsonl")
    p.add_argument("--out_dir", default="data/abstention_ft")
    p.add_argument("--n_train", type=int, default=2000)
    p.add_argument("--n_validate", type=int, default=221)
    p.add_argument("--n_eval", type=int, default=600)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    omni = []
    for i, row in enumerate(read_jsonl(args.omni)):
        row = dict(row)
        row.setdefault("idx", i)
        omni.append(row)

    total_needed = args.n_train + args.n_validate + args.n_eval
    assert len(omni) >= total_needed, (
        f"Dataset has {len(omni)} rows but split needs {total_needed}"
    )

    rng = random.Random(args.seed)
    shuffled = list(omni)
    rng.shuffle(shuffled)

    train_rows = shuffled[: args.n_train]
    validate_rows = shuffled[args.n_train : args.n_train + args.n_validate]
    eval_rows = shuffled[
        args.n_train + args.n_validate : args.n_train + args.n_validate + args.n_eval
    ]

    train_idxs = {str(r["idx"]) for r in train_rows}
    validate_idxs = {str(r["idx"]) for r in validate_rows}
    eval_idxs = {str(r["idx"]) for r in eval_rows}
    assert len(train_idxs) == len(train_rows)
    assert len(validate_idxs) == len(validate_rows)
    assert len(eval_idxs) == len(eval_rows)
    assert not (train_idxs & validate_idxs)
    assert not (train_idxs & eval_idxs)
    assert not (validate_idxs & eval_idxs)

    os.makedirs(args.out_dir, exist_ok=True)
    write_jsonl(train_rows, os.path.join(args.out_dir, "train_candidates.jsonl"))
    write_jsonl(validate_rows, os.path.join(args.out_dir, "validate.jsonl"))
    write_jsonl(eval_rows, os.path.join(args.out_dir, "eval.jsonl"))

    with open(os.path.join(args.out_dir, "split_idxs.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "seed": args.seed,
                "train": sorted(train_idxs, key=int),
                "validate": sorted(validate_idxs, key=int),
                "eval": sorted(eval_idxs, key=int),
            },
            f,
            indent=2,
        )

    print(
        json.dumps(
            {
                "train_candidates": len(train_rows),
                "validate": len(validate_rows),
                "eval": len(eval_rows),
                "total": len(train_rows) + len(validate_rows) + len(eval_rows),
                "seed": args.seed,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
