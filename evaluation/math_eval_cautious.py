#!/usr/bin/env python3
"""Cautious-prompt evaluator for Omni-MATH-Rule.

Per-problem classification:
  - "abstained": deliberate abstention. Either:
        * explicit \\boxed{UNSURE},
        * "Answer/Abstain decision: ABSTAIN" (base-model few-shot), OR
        * NO valid \\boxed{...} produced AND the response was NOT cut by
          the max-token limit (cf. our prompt: "...alternatively, abstain
          by responding with \\boxed{UNSURE}, or not outputting a
          \\boxed{} at all").
    Excluded from accuracy.
  - "indeterminate": no valid \\boxed{...} AND the response was truncated
        by the max-token budget (item's `finish_reason == "length"`).
        The model didn't get a chance to finish — this is *not* a
        deliberate abstain. Excluded from accuracy but reported
        separately.
  - "incorrect_mixed": both UNSURE and non-UNSURE boxed values (scored incorrect).
  - "correct" / "incorrect_standard": graded normally on the last boxed value.

Bug fix: the previous version did `text.split("boxed")` which matched the
substring "boxed" anywhere — including in our prompt's literal
"\\boxed{}" reference and in any prose that happens to contain the word
"boxed". The new extractor requires a *literal* `\\boxed{` opening
sequence (backslash + 'boxed' + '{') and discards empty boxes (e.g. the
model echoing "\\boxed{}" from the instructions).

Usage:
    python evaluation/math_eval_cautious.py \
        --data_file inference/results/GPT-5.2_cautious.jsonl \
        --output_dir evaluation/output/GPT-5.2-cautious/omni-math/
"""

import argparse
import json
import os
import re
import sys

# Allow running from repo root or from evaluation/
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from grader import math_equal
from parser import extract_answer, strip_string


# Matches the abstention marker used in base-model few-shot scaffolding,
# e.g. "Answer/Abstain decision: ABSTAIN" (case-insensitive, tolerant of
# extra whitespace and minor punctuation around the keyword).
_ABSTAIN_MARKER_RE = re.compile(
    r"answer\s*/\s*abstain\s+decision\s*:\s*abstain\b",
    re.IGNORECASE,
)

# Literal `\boxed{` opening — backslash + 'boxed' + '{'. Anchoring on the
# backslash avoids false positives from the substring "boxed" appearing
# in prose ("I'll put my answer in a boxed expression") or in our own
# prompt text ("not outputting a \\boxed{} at all" — when the model
# echoes the instruction).
_BOXED_OPEN_RE = re.compile(r"\\boxed\{")

# Truncation reasons: any of these in the inference item's `finish_reason`
# field signal that the response was cut by the max-token budget, in
# which case a missing \boxed{} should be classified as `indeterminate`
# rather than `abstained`.
_TRUNCATED_FINISH_REASONS = {
    "length", "max_tokens", "max_output_tokens", "model_length",
    "MAX_TOKENS",
}


def has_explicit_abstain_marker(text: str) -> bool:
    return bool(_ABSTAIN_MARKER_RE.search(text or ""))


def is_truncated(item: dict) -> bool:
    """True if the inference item was cut by the max-token budget.

    Looks for `finish_reason` (preferred) or legacy `stop_reason` fields
    on the item; absence of either is treated as 'not truncated' (the
    intervention runner always writes finish_reason).
    """
    fr = item.get("finish_reason") or item.get("stop_reason")
    if fr is None:
        return False
    return str(fr) in _TRUNCATED_FINISH_REASONS


def extract_all_boxed(text: str) -> list[str]:
    """Extract all `\\boxed{<content>}` values from text.

    Requires the literal `\\boxed{` opening (backslash + 'boxed' + '{')
    and uses stack-based brace matching for nested braces. Empty boxes
    (`\\boxed{}`) are dropped — the model is typically echoing our
    prompt's "or not outputting a \\boxed{} at all" reference rather
    than emitting a real answer.
    """
    text = text or ""
    results: list[str] = []
    for m in _BOXED_OPEN_RE.finditer(text):
        i = m.end()  # position right after `\boxed{`
        stack = 1
        buf: list[str] = []
        while i < len(text):
            c = text[i]
            if c == "{":
                stack += 1
                buf.append(c)
            elif c == "}":
                stack -= 1
                if stack == 0:
                    break
                buf.append(c)
            else:
                buf.append(c)
            i += 1
        content = "".join(buf).strip()
        if content:
            results.append(content)
    return results


def is_unsure(value: str) -> bool:
    """Check if a boxed value is UNSURE (case-insensitive, stripped)."""
    return value.strip().upper() == "UNSURE"


def classify_problem(item: dict, data_name: str = "omni-math") -> dict:
    """Classify a single problem's model output.

    Returns a dict with keys: score, category, all_boxed, pred, gt.
    """
    generation = item.get("model_generation", "") or ""
    all_boxed = extract_all_boxed(generation)
    truncated = is_truncated(item)

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
        # No (valid, non-empty) \boxed{...} at all. Three sub-cases:
        if has_explicit_abstain_marker(generation):
            return {
                "score": False,
                "category": "abstained",
                "all_boxed": all_boxed,
                "pred": "ABSTAIN",
                "gt": gt,
            }
        if truncated:
            # The model was cut off by max_tokens before getting to a
            # final \boxed{} — not a deliberate abstain.
            return {
                "score": False,
                "category": "indeterminate",
                "all_boxed": all_boxed,
                "pred": "",
                "gt": gt,
            }
        # Finished cleanly with no \boxed{} — per our prompt this is a
        # valid abstain ("alternatively, ... not outputting a \\boxed{}
        # at all").
        return {
            "score": False,
            "category": "abstained",
            "all_boxed": all_boxed,
            "pred": "NO_BOX",
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

    # No UNSURE — grade on the *last* valid \boxed{...} value.
    # We use our cleanly-extracted box rather than parser.extract_answer()
    # because the latter has the same `split("boxed")` bug and would
    # mis-parse prose containing the word "boxed".
    # `timeout=True` is critical: without it, sympy's `simplify(a - b)`
    # can hang indefinitely on pathological predictions.
    pred = strip_string(all_boxed[-1])
    correct = math_equal(pred, gt, timeout=True)
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
    num_indeterminate = sum(1 for r in results if r["category"] == "indeterminate")
    num_correct = sum(1 for r in results if r["category"] == "correct")
    num_incorrect_standard = sum(1 for r in results if r["category"] == "incorrect_standard")
    num_incorrect_mixed = sum(1 for r in results if r["category"] == "incorrect_mixed")
    # "attempted" excludes both deliberate abstentions and ill-formed outputs.
    num_attempted = num_total - num_abstained - num_indeterminate

    metrics = {
        "num_total": num_total,
        "num_abstained": num_abstained,
        "num_indeterminate": num_indeterminate,
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
