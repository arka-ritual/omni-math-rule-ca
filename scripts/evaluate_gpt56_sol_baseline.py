#!/usr/bin/env python3
"""Evaluate the GPT-5.6 Sol no-consequence baseline in standard format."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from evaluation.math_eval_cautious import classify_problem  # noqa: E402
from scripts.summarize_gpt56_sol import (  # noqa: E402
    Cell,
    expected_indices,
    read_jsonl,
    validate_rows,
)


def evaluate_baseline(data_file: Path, output_dir: Path, dataset_size: int) -> dict:
    rows = read_jsonl(data_file)
    validate_rows(
        rows,
        cell=Cell("baseline", "standard", "standard", "standard"),
        expected_n=100,
        expected_ids=expected_indices(dataset_size, 100),
    )
    if any(row.get("prompt_mode") != "standard" for row in rows):
        raise ValueError("baseline contains a non-standard prompt_mode")

    results = []
    for row in rows:
        result = dict(row)
        result.update(classify_problem(row))
        results.append(result)

    num_correct = sum(result["category"] == "correct" for result in results)
    num_empty = sum(not result["all_boxed"] for result in results)
    num_timeout = sum(result["category"] == "indeterminate" for result in results)
    metrics = {
        "num_samples": len(results),
        "num_scores": len(results),
        "timeout_samples": num_timeout,
        "empty_samples": num_empty,
        "acc": round(100 * num_correct / len(results), 1),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "math_eval.jsonl").open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
    with (output_dir / "math_eval_cot_metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=4)
        handle.write("\n")

    print(f"Validated and evaluated baseline: {metrics}")
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--dataset-file",
        type=Path,
        default=REPO_ROOT / "omni_math_rule.jsonl",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    dataset_size = len(read_jsonl(args.dataset_file))
    evaluate_baseline(args.data_file, args.output_dir, dataset_size)
