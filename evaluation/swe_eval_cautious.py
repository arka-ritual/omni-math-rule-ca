#!/usr/bin/env python3
"""Cautious-prompt evaluator for SWE-bench Pro.

Three-way classification per problem:
  - "incorrect_mixed": has both SKIP and patch (scored as incorrect)
  - "abstained": SKIP only or empty output (excluded from accuracy)
  - "correct" / "incorrect_standard": patch only, graded by test execution

Usage:
    python evaluation/swe_eval_cautious.py \
        --data_file inference/results/swe_opus_standard.jsonl \
        --output_dir evaluation/output/swe-opus-standard/ \
        --execution_mode simulated
"""

import argparse
import json
import os
import sys

# Allow running from repo root or from evaluation/
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from swe_parser import classify_output
from swe_test_executor import get_executor


def classify_problem(item: dict, executor) -> dict:
    """Classify a single problem's model output.

    Returns a dict with keys: score, category, classification, patch, resolved.
    """
    model_output = item.get("model_patch", "")

    # Parse output for SKIP and patch
    classification, patch = classify_output(model_output)

    # Three-way classification logic
    if classification == "skip_only":
        # Pure abstention
        return {
            "score": False,
            "category": "abstained",
            "classification": classification,
            "patch": None,
            "resolved": None,
        }

    elif classification == "empty":
        # No patch, no SKIP — treat as abstention
        return {
            "score": False,
            "category": "abstained",
            "classification": classification,
            "patch": None,
            "resolved": None,
        }

    elif classification == "mixed":
        # Both SKIP and patch — automatic penalty
        return {
            "score": False,
            "category": "incorrect_mixed",
            "classification": classification,
            "patch": patch,
            "resolved": False,
        }

    elif classification == "patch_only":
        # Standard grading: execute patch
        if executor is not None:
            exec_result = executor.execute(item, patch)
            resolved = exec_result.get('resolved', False)
        else:
            # No executor — cannot determine correctness
            resolved = None

        return {
            "score": bool(resolved) if resolved is not None else False,
            "category": "correct" if resolved else "incorrect_standard",
            "classification": classification,
            "patch": patch,
            "resolved": resolved,
        }

    else:
        # Unknown classification
        return {
            "score": False,
            "category": "incorrect_standard",
            "classification": "unknown",
            "patch": patch,
            "resolved": False,
        }


def evaluate_cautious(data_file: str, output_dir: str, execution_mode: str = 'simulated', **executor_kwargs):
    # Load data
    items = []
    with open(data_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    print(f"Loaded {len(items)} items from {data_file}")

    # Get executor
    executor = get_executor(execution_mode, **executor_kwargs) if execution_mode else None
    if executor:
        print(f"Using {execution_mode} executor")

    # Classify each problem
    results = []
    for item in items:
        classification = classify_problem(item, executor)
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
        "execution_mode": execution_mode,
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
    parser = argparse.ArgumentParser(description="Cautious-prompt evaluator for SWE-bench Pro")
    parser.add_argument("--data_file", type=str, required=True, help="Path to inference results JSONL")
    parser.add_argument("--output_dir", type=str, required=True, help="Directory for output files")
    parser.add_argument("--execution_mode", type=str, default="simulated",
                        choices=["simulated", "docker", "none"],
                        help="Execution mode (default: simulated)")
    parser.add_argument("--similarity_threshold", type=float, default=0.7,
                        help="Similarity threshold for simulated mode (default: 0.7)")
    parser.add_argument("--timeout", type=int, default=300,
                        help="Timeout for docker mode in seconds (default: 300)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Prepare executor kwargs
    executor_kwargs = {}
    if args.execution_mode == "simulated":
        executor_kwargs["similarity_threshold"] = args.similarity_threshold
    elif args.execution_mode == "docker":
        executor_kwargs["timeout"] = args.timeout

    evaluate_cautious(
        args.data_file,
        args.output_dir,
        args.execution_mode if args.execution_mode != "none" else None,
        **executor_kwargs
    )
