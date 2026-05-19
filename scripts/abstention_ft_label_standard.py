#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from collections import Counter

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EVAL_DIR = os.path.join(REPO_ROOT, "evaluation")
sys.path.insert(0, EVAL_DIR)

from grader import math_equal
from parser import strip_string


def read_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def extract_all_boxed(text):
    results = []
    parts = text.split("boxed")[1:]

    for part in parts:
        if not part:
            continue

        part = part.lstrip()
        if part.startswith("{"):
            depth = 1
            value = ""
            for c in part[1:]:
                if c == "{":
                    depth += 1
                    value += c
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        break
                    value += c
                else:
                    value += c
            if value.strip():
                results.append(value.strip())
        else:
            value = part.split("$")[0].strip()
            if value:
                results.append(value)

    return results


def extract_final_answer_heuristic(text):
    if not text:
        return None

    boxed = extract_all_boxed(text)
    non_unsure = [b for b in boxed if strip_string(b).upper() != "UNSURE"]
    if non_unsure:
        return non_unsure[-1]

    # Keep this intentionally conservative for standard labeling.
    patterns = [
        r"(?:the\s+)?answer\s+is[:\s]+([^\n.]+)",
        r"final\s+answer\s+is[:\s]+([^\n.]+)",
        r"answer[:\s]+([^\n.]+)",
    ]

    for pat in patterns:
        m = re.findall(pat, text, flags=re.IGNORECASE)
        if m:
            candidate = m[-1].strip().strip("*").strip()
            if candidate and len(candidate) < 200:
                return candidate

    return None


def classify(row):
    generation = row.get("model_generation", "") or ""
    gt = row.get("answer", "")

    pred = extract_final_answer_heuristic(generation)
    if pred is None:
        return "parse_failed", None, False

    pred_s = strip_string(pred)
    gt_s = strip_string(gt)

    try:
        is_correct = bool(math_equal(pred_s, gt_s))
    except Exception:
        is_correct = pred_s == gt_s

    return ("correct" if is_correct else "incorrect"), pred_s, is_correct


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    rows = []
    counts = Counter()

    for row in read_jsonl(args.input):
        classification, extracted, is_correct = classify(row)
        out = dict(row)
        out["classification"] = classification
        out["is_correct"] = is_correct
        out["extracted_answer"] = extracted
        rows.append(out)
        counts[classification] += 1

    write_jsonl(rows, args.output)

    print(json.dumps({
        "input": args.input,
        "output": args.output,
        "total": len(rows),
        "counts": dict(counts),
    }, indent=2))


if __name__ == "__main__":
    main()