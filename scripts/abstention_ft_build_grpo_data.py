#!/usr/bin/env python3
"""Build a GRPO abstention-FT dataset directly from a raw problems split.

Unlike the SFT/DPO builders, GRPO needs no chosen/rejected targets and no
abstention-fraction axis (`p`) — abstention is emergent from the rubric reward.
So we only emit, per problem: the rubric-bearing prompt ([system, user]), the
ground-truth answer (for the reward), and the idx. This decouples GRPO from the
DPO/SFT build files entirely.

Supports the same rubric vocabulary as abstention_ft_build_train_data.py:
  - fixed quantitative rubrics: quant_m0_25 / quant_m1 / quant_m5 / quant_m25 / quant_m100
  - mix rubrics (per-row sampled): mix_m25_m100, mix_m5_m25
  - randomized penalty: quant_randi_<lo>_<hi>  (r_i = -X, X ~ Uniform{lo..hi} per row)

Output row schema (consumed by abstention_ft_train_grpo.py via inline `answer`):
  {prompt: [{role:system,...},{role:user,...}], answer, idx, rubric, row_rubric}

Example:
  python scripts/abstention_ft_build_grpo_data.py \
    --problems data/abstention_ft/train_candidates.jsonl \
    --out data/abstention_ft/gemma4_e2b/grpo_n500_quant_m25.jsonl \
    --rubric quant_m25 --size 500 --seed 42
"""
import argparse
import json
import os
import random
import sys

# Canonical prompt definitions (quant_m5, quant_m1, mix components, …) live in
# inference/prompts.py, matching how abstention_ft_build_train_data.py resolves them.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "inference"))

# Reuse the exact rubric/system-prompt machinery used by the SFT/DPO builder so
# GRPO prompts render identically to the rest of the pipeline. That module sets
# PROMPTS/BUILD_QUANT as globals only inside its own main(), so inject them here.
import abstention_ft_build_train_data as _B
from prompts import PROMPTS as _PROMPTS, build_quantitative_grading as _BQG

_B.PROMPTS = _PROMPTS
_B.BUILD_QUANT = _BQG
_resolve_rubric = _B._resolve_rubric
_system_for_row = _B._system_for_row
problem = _B.problem


def read_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--problems", default="data/abstention_ft/train_candidates.jsonl",
                   help="Raw problems split (needs problem, answer, idx).")
    p.add_argument("--out", required=True)
    p.add_argument("--rubric", default="quant_m25",
                   help="Fixed (quant_m*), mix (mix_*), or randomized (quant_randi_<lo>_<hi>).")
    p.add_argument("--size", type=int, default=500, help="Number of problems (0 = all).")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    canonical, mix_components, _, rand_spec = _resolve_rubric(args.rubric)

    rows = read_jsonl(args.problems)
    missing = [r for r in rows if r.get("answer") in (None, "")]
    rows = [r for r in rows if r.get("answer") not in (None, "")]
    if missing:
        print(f"[grpo-build] skipped {len(missing)} problems without an answer")

    random.Random(args.seed).shuffle(rows)
    if args.size > 0:
        rows = rows[:args.size]

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    n_rub = {}
    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            system, row_rubric = _system_for_row(
                canonical, mix_components, rand_spec, r["idx"], args.seed)
            n_rub[row_rubric] = n_rub.get(row_rubric, 0) + 1
            f.write(json.dumps({
                "prompt": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": problem(r)},
                ],
                "answer": str(r["answer"]),
                "idx": r["idx"],
                "rubric": canonical,
                "row_rubric": row_rubric,
            }, ensure_ascii=False) + "\n")

    print(f"[grpo-build] wrote {len(rows)} prompts -> {args.out} "
          f"(rubric={canonical}, per-row rubric dist: {dict(sorted(n_rub.items()))})")


if __name__ == "__main__":
    main()
