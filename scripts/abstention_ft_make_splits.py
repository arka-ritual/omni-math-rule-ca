#!/usr/bin/env python3
import argparse
import json
import os


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
    p.add_argument("--eval_file", default="inference/results/eval.jsonl")
    p.add_argument("--out_dir", default="data/abstention_ft")
    args = p.parse_args()

    omni = []
    for i, row in enumerate(read_jsonl(args.omni)):
        row = dict(row)
        row.setdefault("idx", i)
        omni.append(row)

    standard = read_jsonl(args.eval_file)
    n_eval = len(standard)
    assert n_eval == 99, f"Expected 99 eval rows, got {n_eval}"
    assert all("idx" in row for row in standard), "Every eval row must have idx"

    eval_idxs = {str(row["idx"]) for row in standard}
    assert len(eval_idxs) == n_eval, f"duplicate idxs in eval file: {n_eval} rows but {len(eval_idxs)} unique"

    omni_idxs = {str(row["idx"]) for row in omni}
    missing = eval_idxs - omni_idxs
    assert not missing, f"eval idxs missing from omni: {sorted(missing)[:20]}"

    eval_rows = [row for row in omni if str(row["idx"]) in eval_idxs]
    train = [row for row in omni if str(row["idx"]) not in eval_idxs]
    assert len(eval_rows) == n_eval
    assert not (eval_idxs & {str(row["idx"]) for row in train})

    os.makedirs(args.out_dir, exist_ok=True)
    write_jsonl(eval_rows, os.path.join(args.out_dir, "eval.jsonl"))
    write_jsonl(train, os.path.join(args.out_dir, "train_candidates.jsonl"))
    with open(os.path.join(args.out_dir, "eval_idxs.json"), "w", encoding="utf-8") as f:
        json.dump(sorted(eval_idxs, key=int), f, indent=2)

    print(json.dumps({"eval_rows": len(eval_rows), "train_candidates": len(train)}, indent=2))


if __name__ == "__main__":
    main()
