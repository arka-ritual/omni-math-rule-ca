#!/usr/bin/env python3
"""Natural-grading evaluator for Omni-MATH-Rule.

Handles responses that may or may not use \boxed{}. For non-boxed responses,
extracts the final answer heuristically (bold text, "= X", last number, etc.).

Uses the same 3-way cautious classification:
  - "abstained": no discernible final answer
  - "correct" / "incorrect_standard": graded against ground truth

Usage:
    python evaluation/math_eval_natural.py \
        --data_file inference/results/opus-4.6-natural_grading.jsonl \
        --output_dir evaluation/output/opus-4.6-natural_grading
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from grader import math_equal
from parser import extract_answer, strip_string


def extract_all_boxed(text: str) -> list[str]:
    """Extract all \\boxed{...} values from text using stack-based brace matching."""
    results = []
    parts = text.split("boxed")[1:]
    for part in parts:
        if not part or part[0] != "{":
            val = part.split("$")[0].strip() if part else ""
            if val:
                results.append(val)
            continue
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
        if a:
            results.append(a)
    return results


def extract_final_answer_heuristic(text: str) -> str | None:
    """Try to extract a final answer from free-form text without \\boxed{}.

    Strategies (in order):
    1. Look for bold answer patterns like **answer** at the end
    2. Look for "= **X**" or "= X" near the end
    3. Look for "answer is X" / "answer: X" patterns
    """
    if not text:
        return None

    # Strategy 1: Last bold value (common pattern: "The answer is **42**.")
    bold_pattern = re.findall(r'\*\*([^*]+)\*\*', text)
    if bold_pattern:
        # Take the last bold value — often the final answer
        candidate = bold_pattern[-1].strip().rstrip(".")
        # Filter out non-answer bolds (headers, labels)
        # If it looks like a section header, skip it
        if len(candidate) < 100 and not candidate.endswith(":"):
            return candidate

    # Strategy 2: "answer is X" or "answer: X" (case insensitive)
    answer_patterns = re.findall(
        r'(?:the\s+)?answer\s+is[:\s]+([^\n.]+)', text, re.IGNORECASE
    )
    if answer_patterns:
        candidate = answer_patterns[-1].strip().rstrip(".")
        # Remove surrounding bold markers
        candidate = candidate.strip("*").strip()
        if candidate:
            return candidate

    # Strategy 3: Last "= value" in the text
    equals_pattern = re.findall(r'=\s*([^\n=,]+?)(?:\s*$|\s*\n)', text)
    if equals_pattern:
        candidate = equals_pattern[-1].strip().rstrip(".").strip("*").strip()
        if candidate:
            return candidate

    return None


def classify_problem(item: dict) -> dict:
    """Classify a single problem result."""
    generation = item.get("model_generation", "") or ""
    gt_answer = item.get("answer", "")

    # First try boxed extraction
    all_boxed = extract_all_boxed(generation)

    if all_boxed:
        # Has boxed values — check for UNSURE
        has_unsure = any(
            strip_string(b).upper() == "UNSURE" for b in all_boxed
        )
        non_unsure = [b for b in all_boxed if strip_string(b).upper() != "UNSURE"]

        if has_unsure and non_unsure:
            return {"category": "incorrect_mixed", "extracted": all_boxed}
        if has_unsure and not non_unsure:
            return {"category": "abstained", "extracted": all_boxed}

        # Standard grading on last boxed value
        pred = strip_string(all_boxed[-1])
        gt = strip_string(gt_answer)
        correct = math_equal(pred, gt)
        return {
            "category": "correct" if correct else "incorrect_standard",
            "extracted": pred,
        }

    # No boxed values — try heuristic extraction
    extracted = extract_final_answer_heuristic(generation)

    if extracted is None:
        return {"category": "abstained", "extracted": None}

    # Grade the extracted answer
    pred = strip_string(extracted)
    gt = strip_string(gt_answer)
    correct = math_equal(pred, gt)
    return {
        "category": "correct" if correct else "incorrect_standard",
        "extracted": pred,
    }


def evaluate_natural(data_file: str, output_dir: str):
    """Run natural evaluation on a results JSONL."""
    with open(data_file, "r", encoding="utf-8") as f:
        samples = [json.loads(line) for line in f if line.strip()]

    results = []
    counts = {
        "correct": 0,
        "incorrect_standard": 0,
        "incorrect_mixed": 0,
        "abstained": 0,
    }

    for item in samples:
        classification = classify_problem(item)
        counts[classification["category"]] += 1
        results.append({
            "idx": item.get("idx"),
            "answer": item.get("answer"),
            "category": classification["category"],
            "extracted": classification["extracted"],
        })

    num_attempted = counts["correct"] + counts["incorrect_standard"] + counts["incorrect_mixed"]
    acc = round(100 * counts["correct"] / num_attempted, 1) if num_attempted > 0 else 0.0

    metrics = {
        "num_total": len(samples),
        "num_abstained": counts["abstained"],
        "num_attempted": num_attempted,
        "num_correct": counts["correct"],
        "num_incorrect_standard": counts["incorrect_standard"],
        "num_incorrect_mixed": counts["incorrect_mixed"],
        "accuracy_of_attempted": acc,
    }

    os.makedirs(os.path.join(output_dir, "omni-math"), exist_ok=True)
    metrics_path = os.path.join(output_dir, "omni-math", "cautious_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    details_path = os.path.join(output_dir, "omni-math", "natural_grading_details.jsonl")
    with open(details_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(json.dumps(metrics, indent=2))
    return metrics


def parse_args():
    parser = argparse.ArgumentParser(description="Natural-grading evaluator for Omni-MATH-Rule")
    parser.add_argument("--data_file", type=str, required=True, help="Path to inference results JSONL")
    parser.add_argument("--output_dir", type=str, required=True, help="Directory for output files")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    evaluate_natural(args.data_file, args.output_dir)
