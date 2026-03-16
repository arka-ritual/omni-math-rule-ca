#!/usr/bin/env python3
"""Evaluator for sequential adaptive environment runs.

Computes cumulative score, calibration metrics, and per-difficulty breakdowns.

Usage:
    python evaluation/math_eval_sequential.py \
        --data_file inference/results/seq_opus-4.6_summary.jsonl \
        --output_dir evaluation/output/seq-opus-4.6-summary/
"""

import argparse
import json
import os


def evaluate_sequential(data_file: str, output_dir: str):
    with open(data_file, "r", encoding="utf-8") as f:
        steps = [json.loads(line) for line in f if line.strip()]

    if not steps:
        print("No steps found.")
        return

    rubric = steps[0].get("rubric", {"correct": 1, "incorrect": -10, "skip": 0})

    correct = [s for s in steps if s["outcome"] == "correct"]
    incorrect = [s for s in steps if s["outcome"] == "incorrect"]
    skipped = [s for s in steps if s["outcome"] == "skipped"]
    timed_out = [s for s in steps if s["outcome"] == "timed_out"]
    attempted = correct + incorrect

    final_score = steps[-1]["cumulative_score"]
    score_trajectory = [s["cumulative_score"] for s in steps]

    # Oracle: answer all correctly answerable, skip rest
    oracle_score = (
        len(correct) * rubric["correct"]
        + (len(incorrect) + len(skipped) + len(timed_out)) * rubric["skip"]
    )

    # Naive: answer everything (no skipping)
    naive_score = (
        len(correct) * rubric["correct"]
        + (len(incorrect) + len(skipped) + len(timed_out)) * rubric["incorrect"]
    )

    # Per-difficulty breakdown
    difficulty_buckets: dict[str, dict] = {}
    for s in steps:
        d = s.get("difficulty", 0)
        bucket = f"{int(d)}-{int(d) + 1}"
        if bucket not in difficulty_buckets:
            difficulty_buckets[bucket] = {"correct": 0, "incorrect": 0, "skipped": 0, "timed_out": 0, "total": 0}
        difficulty_buckets[bucket][s["outcome"]] += 1
        difficulty_buckets[bucket]["total"] += 1

    # Adaptive behavior: skip rate over time (first half vs second half)
    half = len(steps) // 2
    first_half = steps[:half]
    second_half = steps[half:]
    first_skip_rate = sum(1 for s in first_half if s["outcome"] == "skipped") / len(first_half) if first_half else 0
    second_skip_rate = sum(1 for s in second_half if s["outcome"] == "skipped") / len(second_half) if second_half else 0

    metrics = {
        "final_score": final_score,
        "total_steps": len(steps),
        "correct": len(correct),
        "incorrect": len(incorrect),
        "skipped": len(skipped),
        "timed_out": len(timed_out),
        "accuracy_when_attempted": round(100 * len(correct) / len(attempted), 1) if attempted else 0.0,
        "attempt_rate": round(100 * len(attempted) / len(steps), 1),
        "skip_rate": round(100 * len(skipped) / len(steps), 1),
        "oracle_score": oracle_score,
        "naive_always_answer_score": naive_score,
        "skip_rate_first_half": round(100 * first_skip_rate, 1),
        "skip_rate_second_half": round(100 * second_skip_rate, 1),
        "score_trajectory": score_trajectory,
        "per_difficulty": dict(sorted(difficulty_buckets.items())),
        "rubric": rubric,
    }

    os.makedirs(output_dir, exist_ok=True)
    metrics_path = os.path.join(output_dir, "sequential_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print(json.dumps({k: v for k, v in metrics.items() if k != "score_trajectory"}, indent=2))
    return metrics


def parse_args():
    parser = argparse.ArgumentParser(description="Sequential environment evaluator")
    parser.add_argument("--data_file", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    evaluate_sequential(args.data_file, args.output_dir)
