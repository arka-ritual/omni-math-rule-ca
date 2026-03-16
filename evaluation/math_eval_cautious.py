#!/usr/bin/env python3
"""Cautious-prompt evaluator for Omni-MATH-Rule.

Three-way classification per problem:
  - "incorrect_mixed": has both UNSURE and non-UNSURE boxed values (scored as incorrect)
  - "abstained": all boxed values are UNSURE (ignored from accuracy)
  - "correct" / "incorrect_standard": no UNSURE boxed values, graded normally

Usage:
    python evaluation/math_eval_cautious.py \
        --data_file inference/results/GPT-5.2_cautious.jsonl \
        --output_dir evaluation/output/GPT-5.2-cautious/omni-math/
"""

import argparse
import json
import os
import sys

# Allow running from repo root or from evaluation/
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from grader import math_equal
from parser import extract_answer, strip_string


def extract_all_boxed(text: str) -> list[str]:
    """Extract all \\boxed{...} values from text using stack-based brace matching."""
    results = []
    parts = text.split("boxed")[1:]  # everything after each 'boxed' occurrence
    for part in parts:
        if not part or part[0] != "{":
            # No brace — take up to next $ or whitespace
            val = part.split("$")[0].strip() if part else ""
            if val:
                results.append(val)
            continue
        # Stack-based brace matching (mirrors parser.py:find_box)
        stack = 1
        a = ""
        for c in part[1:]:
            if c == "{":
                stack += 1
                a += c
            elif c == "}":
                stack -= 1
                if stack == 0:
                    break
                a += c
            else:
                a += c
        results.append(a)
    return results


def is_unsure(value: str) -> bool:
    """Check if a boxed value is UNSURE (case-insensitive, stripped)."""
    return value.strip().upper() == "UNSURE"


def classify_problem(item: dict, data_name: str = "omni-math") -> dict:
    """Classify a single problem's model output.

    Returns a dict with keys: score, category, all_boxed, pred, gt.
    """
    generation = item.get("model_generation", "")
    all_boxed = extract_all_boxed(generation)

    # Ground truth: use 'answer' field directly (Omni-MATH-Rule format)
    gt_raw = item.get("answer", "")
    if "solution" in item:
        gt_cot = item["solution"]
        if "boxed" not in gt_cot:
            gt_cot = "\\boxed{" + gt_raw + "}"
        gt = extract_answer(gt_cot, data_name)
    else:
        gt = strip_string(gt_raw)

    unsure_flags = [is_unsure(v) for v in all_boxed]
    has_unsure = any(unsure_flags)
    has_non_unsure = any(not f for f in unsure_flags)

    if not all_boxed:
        # No boxed output at all — treat as abstained
        return {
            "score": False,
            "category": "abstained",
            "all_boxed": all_boxed,
            "pred": "",
            "gt": gt,
        }

    if has_unsure and has_non_unsure:
        # Mixed: both UNSURE and real answers — automatic penalty
        return {
            "score": False,
            "category": "incorrect_mixed",
            "all_boxed": all_boxed,
            "pred": "[MIXED]",
            "gt": gt,
        }

    if has_unsure and not has_non_unsure:
        # Pure UNSURE — abstained
        return {
            "score": False,
            "category": "abstained",
            "all_boxed": all_boxed,
            "pred": "UNSURE",
            "gt": gt,
        }

    # No UNSURE — standard grading using last boxed value
    pred = extract_answer(generation, data_name)
    correct = math_equal(pred, gt)
    return {
        "score": bool(correct),
        "category": "correct" if correct else "incorrect_standard",
        "all_boxed": all_boxed,
        "pred": pred,
        "gt": gt,
    }


def evaluate_cautious(data_file: str, output_dir: str):
    # Load data
    items = []
    with open(data_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    print(f"Loaded {len(items)} items from {data_file}")

    # Classify each problem
    results = []
    for item in items:
        classification = classify_problem(item)
        result = dict(item)
        result.update(classification)
        results.append(result)

    # Compute metrics
    num_total = len(results)
    num_abstained = sum(1 for r in results if r["category"] == "abstained")
    num_correct = sum(1 for r in results if r["category"] == "correct")
    num_incorrect_standard = sum(1 for r in results if r["category"] == "incorrect_standard")
    num_incorrect_mixed = sum(1 for r in results if r["category"] == "incorrect_mixed")
    num_attempted = num_total - num_abstained

    metrics = {
        "num_total": num_total,
        "num_abstained": num_abstained,
        "num_attempted": num_attempted,
        "num_correct": num_correct,
        "num_incorrect_standard": num_incorrect_standard,
        "num_incorrect_mixed": num_incorrect_mixed,
        "accuracy_of_attempted": round(100 * num_correct / num_attempted, 1) if num_attempted > 0 else 0.0,
    }

    # Save outputs
    os.makedirs(output_dir, exist_ok=True)

    metrics_path = os.path.join(output_dir, "cautious_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to {metrics_path}")

    details_path = os.path.join(output_dir, "cautious_eval.jsonl")
    with open(details_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Per-problem results saved to {details_path}")

    # Print summary
    print("\n=== Cautious Evaluation Summary ===")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    return metrics


def parse_args():
    parser = argparse.ArgumentParser(description="Cautious-prompt evaluator for Omni-MATH-Rule")
    parser.add_argument("--data_file", type=str, required=True, help="Path to inference results JSONL")
    parser.add_argument("--output_dir", type=str, required=True, help="Directory for output files")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    evaluate_cautious(args.data_file, args.output_dir)
