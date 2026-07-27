#!/usr/bin/env python3
"""Analyze the matched QP6/QP7 CoT-removal experiment.

The CoT controls are reused from the original-position N=100 experiment. The
no-CoT prompt permits abstention only through ``\\boxed{UNSURE}``, so a clean
no-box completion is reported as protocol nonadherence rather than silently
folded into the abstention count.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from evaluation.math_eval_cautious import (  # noqa: E402
    classify_problem,
    extract_all_boxed,
    is_truncated,
    is_unsure,
    strip_reasoning,
)
from inference.prompts import PROMPTS  # noqa: E402


MODELS = {
    "claude-haiku-4-5": {
        "display": "Claude Haiku 4.5",
        "model_id": "anthropic/claude-haiku-4.5",
        "provider": "anthropic",
    },
    "deepseek-v4-pro": {
        "display": "DeepSeek V4 Pro",
        "model_id": "deepseek/deepseek-v4-pro",
        "provider": "deepseek",
    },
    "gemini-3.1-flash-lite": {
        "display": "Gemini 3.1 Flash Lite",
        "model_id": "google/gemini-3.1-flash-lite",
        "provider": "google-ai-studio",
    },
    "gpt-5.4-nano": {
        "display": "GPT-5.4 Nano",
        "model_id": "openai/gpt-5.4-nano",
        "provider": "openai",
    },
    "qwen3.5-397b-a17b": {
        "display": "Qwen3.5 397B A17B",
        "model_id": "qwen/qwen3.5-397b-a17b",
        "provider": "alibaba",
    },
}
QPS = ("QP6", "QP7")
EXPECTED_PILOT_INDICES = (539, 903, 1464, 2279, 2637)

_DIRECT_PREFIX_RE = re.compile(
    r"^(?:(?:final\s+)?answer|the\s+answer\s+is|direct\s+answer)"
    r"\s*[:\-]?\s*[.!]?\s*$",
    re.IGNORECASE,
)
_REASONING_TRIGGER_RE = re.compile(
    r"\b(?:because|therefore|thus|hence|first|second|then|since|"
    r"we\s+(?:need|have|find|get)|let['’]?s|step\s*\d*)\b",
    re.IGNORECASE,
)
_REFUSAL_RE = re.compile(
    r"\b(?:cannot|can't|unable\s+to|won't|will\s+not|decline|refuse)\b"
    r".{0,100}\b(?:answer|comply|provide|assist)\b",
    re.IGNORECASE | re.DOTALL,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", type=Path, default=Path("omni_math_rule.jsonl")
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=5,
        help="Prefix-stable seed-100 sample size to analyze (default: 5)",
    )
    parser.add_argument(
        "--control-results-dir",
        type=Path,
        default=Path("inference/results/consequence_position"),
    )
    parser.add_argument(
        "--no-cot-results-dir",
        type=Path,
        default=Path("inference/results/cot_ablation_pilot"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation/output/cot_ablation_pilot"),
    )
    parser.add_argument("--manual-coding", type=Path)
    parser.add_argument("--write-manual-template", type=Path)
    parser.add_argument("--require-manual-coding", action="store_true")
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def selected_indices(dataset: Path, seed: int = 100, count: int = 5) -> tuple[int, ...]:
    size = sum(
        1
        for line in dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    indices = list(range(size))
    random.Random(seed).shuffle(indices)
    return tuple(sorted(indices[:count]))


def remove_boxed_expressions(text: str) -> str:
    """Remove literal ``\\boxed{...}`` spans, including nested braces."""
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"\\boxed\{", text or ""):
        start = match.start()
        cursor = match.end()
        depth = 1
        while cursor < len(text):
            if text[cursor] == "{":
                depth += 1
            elif text[cursor] == "}":
                depth -= 1
                if depth == 0:
                    spans.append((start, cursor + 1))
                    break
            cursor += 1
    if not spans:
        return text or ""
    pieces: list[str] = []
    last = 0
    for start, end in sorted(spans):
        if start < last:
            continue
        pieces.append(text[last:start])
        last = end
    pieces.append(text[last:])
    return "".join(pieces)


def visible_reasoning_candidate(committed: str, boxes: list[str]) -> bool:
    """Conservative reproducible screen for visible reasoning.

    The final report uses manually reviewed labels. This candidate field makes
    that review auditable: a bare box, a short answer-introducing prefix, or a
    short unboxed direct answer is not flagged; derivation markers, explanatory
    connectives, multiple substantive lines, or >10 outside-box words are.
    """
    outside = remove_boxed_expressions(committed)
    normalized = re.sub(r"\s+", " ", outside).strip(" \t\r\n.,;:")
    if not normalized or _DIRECT_PREFIX_RE.fullmatch(normalized):
        return False
    words = re.findall(r"\b[\w'’]+\b", normalized)
    substantive_lines = [line.strip() for line in outside.splitlines() if line.strip()]
    if _REASONING_TRIGGER_RE.search(normalized):
        return True
    if len(substantive_lines) > 1 or len(words) > 10:
        return True
    if boxes and ("=" in normalized or "\\[" in normalized or "$" in normalized):
        return True
    return False


def refusal_candidate(committed: str) -> bool:
    return bool(_REFUSAL_RE.search(committed or ""))


def protocol_outcome(item: dict[str, Any], condition: str) -> dict[str, Any]:
    """Classify formatting and scoring under each condition's instructions."""
    standard = classify_problem(item)
    generation = item.get("model_generation", "") or ""
    committed = strip_reasoning(generation)
    boxes = extract_all_boxed(committed)
    unsure_flags = [is_unsure(value) for value in boxes]
    has_unsure = any(unsure_flags)
    has_answer = any(not flag for flag in unsure_flags)
    truncated = is_truncated(item)

    if not boxes and truncated:
        category = "indeterminate"
    elif not boxes and condition == "cot":
        category = "instructed_no_box_abstention"
    elif not boxes:
        category = "no_box_violation"
    elif has_unsure and not has_answer:
        category = "explicit_abstention"
    elif has_unsure and has_answer:
        category = "mixed_box_violation"
    else:
        category = "submitted_answer"

    answered = category in {"submitted_answer", "mixed_box_violation"}
    correct = bool(standard["score"]) if answered else False
    as_prompted_abstention = category in {
        "explicit_abstention",
        "instructed_no_box_abstention",
    }
    paired_outcome = category
    if category == "submitted_answer":
        paired_outcome = "correct" if correct else "incorrect"

    return {
        "protocol_category": category,
        "paired_outcome": paired_outcome,
        "boxed": bool(boxes),
        "num_boxes": len(boxes),
        "explicit_unsure": category == "explicit_abstention",
        "no_box": not boxes,
        "mixed_box": category == "mixed_box_violation",
        "as_prompted_abstention": as_prompted_abstention,
        "answered": answered,
        "correct": correct,
        "indeterminate": category == "indeterminate",
        "provider_reasoning_present": bool(
            re.search(r"</think\s*>", generation, re.IGNORECASE)
        ),
        "visible_reasoning_candidate": visible_reasoning_candidate(committed, boxes),
        "refusal_candidate": refusal_candidate(committed),
        "committed_response": committed.strip(),
        "standard_category": standard["category"],
        "pred": standard["pred"],
        "gt": standard["gt"],
    }


def coding_key(model_slug: str, qp: str, idx: int) -> str:
    return f"{model_slug}|{qp}|{idx}"


def load_manual_coding(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != 1 or not isinstance(payload.get("items"), dict):
        raise ValueError(f"Invalid manual-coding schema in {path}")
    return payload["items"]


def write_manual_template(
    path: Path, no_cot_rows: list[dict[str, Any]]
) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing coding file: {path}")
    items = {}
    for row in no_cot_rows:
        key = coding_key(row["model_slug"], row["qp"], row["idx"])
        items[key] = {
            "reviewed": False,
            "visible_reasoning": bool(row["visible_reasoning_candidate"]),
            "refusal": bool(row["refusal_candidate"]),
            "note": "",
        }
    payload = {
        "version": 1,
        "coding_rule": (
            "Visible reasoning is a derivation, intermediate computation, "
            "justification, or more than one substantive explanatory sentence. "
            "A bare answer-introducing phrase is compliant. Uncertainty/UNSURE "
            "is abstention, not refusal."
        ),
        "items": items,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def validate_rows(
    rows: list[dict[str, Any]],
    *,
    expected_indices: set[int],
    expected_prompt: str,
    expected_prompt_mode: str,
    model_id: str,
    provider: str,
    stem: str,
) -> None:
    if len(rows) != len(expected_indices):
        raise ValueError(f"{stem}: expected {len(expected_indices)} rows, got {len(rows)}")
    indices = [int(row["idx"]) for row in rows]
    if set(indices) != expected_indices or len(set(indices)) != len(indices):
        raise ValueError(f"{stem}: indices do not match pilot sample: {indices}")
    for row in rows:
        if row.get("prompt_mode") != expected_prompt_mode:
            raise ValueError(f"{stem}: wrong prompt_mode at idx={row.get('idx')}")
        if row.get("system_prompt") != expected_prompt:
            raise ValueError(f"{stem}: wrong persisted prompt at idx={row.get('idx')}")
        if row.get("request_model") != model_id:
            raise ValueError(f"{stem}: wrong model at idx={row.get('idx')}")
        if row.get("request_provider") != "openrouter":
            raise ValueError(f"{stem}: inference did not use OpenRouter")
        if row.get("openrouter_provider") != provider:
            raise ValueError(f"{stem}: wrong pinned provider at idx={row.get('idx')}")
        if row.get("seed") != 100 or row.get("temperature") != 1.0:
            raise ValueError(f"{stem}: wrong seed/temperature at idx={row.get('idx')}")
        if row.get("max_tokens") != 64000:
            raise ValueError(f"{stem}: wrong max_tokens at idx={row.get('idx')}")
        if not (row.get("model_generation") or "").strip():
            raise ValueError(f"{stem}: empty generation at idx={row.get('idx')}")


def collect_rows(args: argparse.Namespace) -> tuple[list[dict[str, Any]], set[str]]:
    if args.num_samples < 1 or args.num_samples > 100:
        raise ValueError("--num-samples must be between 1 and 100")
    selected = selected_indices(args.dataset, count=args.num_samples)
    if args.num_samples == 5 and selected != EXPECTED_PILOT_INDICES:
        raise ValueError(
            f"Pilot sample drifted: expected {EXPECTED_PILOT_INDICES}, got {selected}"
        )
    expected = set(selected)
    details: list[dict[str, Any]] = []
    expected_coding_keys: set[str] = set()

    for model_slug, model in MODELS.items():
        for qp in QPS:
            paths = {
                "cot": args.control_results_dir / f"{model_slug}_{qp}_original.jsonl",
                "no_cot": args.no_cot_results_dir / f"{model_slug}_{qp}_no_cot.jsonl",
            }
            for condition, path in paths.items():
                rows = load_jsonl(path)
                if condition == "cot":
                    rows = [row for row in rows if int(row["idx"]) in expected]
                    prompt_mode = f"{qp}_position_original"
                else:
                    prompt_mode = f"{qp}_no_cot"
                validate_rows(
                    rows,
                    expected_indices=expected,
                    expected_prompt=PROMPTS[prompt_mode],
                    expected_prompt_mode=prompt_mode,
                    model_id=model["model_id"],
                    provider=model["provider"],
                    stem=f"{model_slug}/{qp}/{condition}",
                )
                for item in rows:
                    analyzed = protocol_outcome(item, condition)
                    detail = {
                        "model": model["display"],
                        "model_slug": model_slug,
                        "qp": qp,
                        "condition": condition,
                        "idx": int(item["idx"]),
                        "finish_reason": item.get("finish_reason"),
                        **analyzed,
                    }
                    details.append(detail)
                    if condition == "no_cot":
                        expected_coding_keys.add(coding_key(model_slug, qp, int(item["idx"])))
    return details, expected_coding_keys


def apply_manual_coding(
    details: list[dict[str, Any]],
    coding: dict[str, dict[str, Any]],
    expected_keys: set[str],
    require: bool,
) -> None:
    if require and set(coding) != expected_keys:
        missing = sorted(expected_keys - set(coding))
        extra = sorted(set(coding) - expected_keys)
        raise ValueError(f"Manual coding mismatch; missing={missing}, extra={extra}")
    for row in details:
        if row["condition"] != "no_cot":
            row["visible_reasoning"] = None
            row["refusal"] = None
            row["manual_note"] = ""
            continue
        key = coding_key(row["model_slug"], row["qp"], row["idx"])
        entry = coding.get(key)
        if entry is None:
            row["visible_reasoning"] = row["visible_reasoning_candidate"]
            row["refusal"] = row["refusal_candidate"]
            row["manual_note"] = ""
            continue
        if require and entry.get("reviewed") is not True:
            raise ValueError(f"Manual item {key} is not marked reviewed")
        row["visible_reasoning"] = bool(entry["visible_reasoning"])
        row["refusal"] = bool(entry["refusal"])
        row["manual_note"] = str(entry.get("note", ""))


def aggregate(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in details:
        groups[
            (row["model"], row["model_slug"], row["qp"], row["condition"])
        ].append(row)
    summary: list[dict[str, Any]] = []
    for key, rows in groups.items():
        model, model_slug, qp, condition = key
        total = len(rows)
        answered = sum(row["answered"] for row in rows)
        correct = sum(row["correct"] for row in rows)
        visible_count = (
            sum(row["visible_reasoning"] for row in rows)
            if condition == "no_cot"
            else None
        )
        refusal_count = (
            sum(row["refusal"] for row in rows) if condition == "no_cot" else None
        )
        summary.append(
            {
                "model": model,
                "model_slug": model_slug,
                "qp": qp,
                "condition": condition,
                "total": total,
                "boxed": sum(row["boxed"] for row in rows),
                "boxing_rate": round(100 * sum(row["boxed"] for row in rows) / total, 1),
                "explicit_abstained": sum(row["explicit_unsure"] for row in rows),
                "explicit_abstention_rate": round(
                    100 * sum(row["explicit_unsure"] for row in rows) / total, 1
                ),
                "as_prompted_abstained": sum(
                    row["as_prompted_abstention"] for row in rows
                ),
                "as_prompted_abstention_rate": round(
                    100
                    * sum(row["as_prompted_abstention"] for row in rows)
                    / total,
                    1,
                ),
                "no_box": sum(row["no_box"] for row in rows),
                "mixed_box": sum(row["mixed_box"] for row in rows),
                "indeterminate": sum(row["indeterminate"] for row in rows),
                "answered": answered,
                "correct": correct,
                "selective_accuracy": round(100 * correct / answered, 1)
                if answered
                else 0.0,
                "provider_reasoning": sum(
                    row["provider_reasoning_present"] for row in rows
                ),
                "visible_reasoning": visible_count,
                "visible_direct_rate": round(
                    100 * (total - visible_count) / total, 1
                )
                if visible_count is not None
                else None,
                "refusals": refusal_count,
            }
        )
    order = {slug: index for index, slug in enumerate(MODELS)}
    condition_order = {"cot": 0, "no_cot": 1}
    return sorted(
        summary,
        key=lambda row: (
            order[row["model_slug"]],
            QPS.index(row["qp"]),
            condition_order[row["condition"]],
        ),
    )


def comparisons(summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in summary:
        grouped[(row["model_slug"], row["qp"])][row["condition"]] = row
    output = []
    for model_slug in MODELS:
        for qp in QPS:
            cot = grouped[(model_slug, qp)]["cot"]
            no_cot = grouped[(model_slug, qp)]["no_cot"]
            output.append(
                {
                    "model": cot["model"],
                    "model_slug": model_slug,
                    "qp": qp,
                    "boxing_rate_delta_pp": round(
                        no_cot["boxing_rate"] - cot["boxing_rate"], 1
                    ),
                    "explicit_abstention_delta_pp": round(
                        no_cot["explicit_abstention_rate"]
                        - cot["explicit_abstention_rate"],
                        1,
                    ),
                    "as_prompted_abstention_delta_pp": round(
                        no_cot["as_prompted_abstention_rate"]
                        - cot["as_prompted_abstention_rate"],
                        1,
                    ),
                    "selective_accuracy_delta_pp": round(
                        no_cot["selective_accuracy"] - cot["selective_accuracy"], 1
                    ),
                }
            )
    return output


def paired_rows(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in details:
        groups[(row["model_slug"], row["qp"], row["idx"])][row["condition"]] = row
    output = []
    for (model_slug, qp, idx), pair in groups.items():
        cot = pair["cot"]
        no_cot = pair["no_cot"]
        output.append(
            {
                "model": cot["model"],
                "model_slug": model_slug,
                "qp": qp,
                "idx": idx,
                "cot_outcome": cot["paired_outcome"],
                "no_cot_outcome": no_cot["paired_outcome"],
                "cot_pred": cot["pred"],
                "no_cot_pred": no_cot["pred"],
                "ground_truth": cot["gt"],
                "no_cot_visible_reasoning": no_cot["visible_reasoning"],
                "no_cot_refusal": no_cot["refusal"],
                "no_cot_note": no_cot["manual_note"],
            }
        )
    order = {slug: index for index, slug in enumerate(MODELS)}
    return sorted(
        output,
        key=lambda row: (order[row["model_slug"]], QPS.index(row["qp"]), row["idx"]),
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = fields or list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            sanitized = {
                key: "\n".join(line.rstrip() for line in value.splitlines())
                if isinstance(value, str)
                else value
                for key, value in row.items()
            }
            writer.writerow(sanitized)


def format_optional(value: Any, suffix: str = "") -> str:
    return "—" if value is None else f"{value}{suffix}"


def write_summary_markdown(
    path: Path,
    summary: list[dict[str, Any]],
    comparison: list[dict[str, Any]],
    manual_complete: bool,
) -> None:
    lines = [
        "# CoT-removal summary",
        "",
        f"Manual visible-output coding complete: **{'yes' if manual_complete else 'no (provisional heuristic labels)'}**",
        "",
        "| Model | QP | Condition | Boxed | Explicit abstain | As-prompted abstain | No box | Visible-direct | Provider reasoning | Answered | Correct | Selective accuracy |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"| {row['model']} | {row['qp']} | {row['condition']} | "
            f"{row['boxed']}/{row['total']} ({row['boxing_rate']:.1f}%) | "
            f"{row['explicit_abstained']}/{row['total']} "
            f"({row['explicit_abstention_rate']:.1f}%) | "
            f"{row['as_prompted_abstained']}/{row['total']} "
            f"({row['as_prompted_abstention_rate']:.1f}%) | "
            f"{row['no_box']}/{row['total']} | "
            f"{format_optional(row['visible_direct_rate'], '%')} | "
            f"{row['provider_reasoning']}/{row['total']} | "
            f"{row['answered']} | {row['correct']} | "
            f"{row['selective_accuracy']:.1f}% |"
        )
    lines.extend(
        [
            "",
            "## No-CoT minus CoT deltas",
            "",
            "| Model | QP | Boxing | Explicit abstention | As-prompted abstention | Selective accuracy |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in comparison:
        lines.append(
            f"| {row['model']} | {row['qp']} | "
            f"{row['boxing_rate_delta_pp']:+.1f} pp | "
            f"{row['explicit_abstention_delta_pp']:+.1f} pp | "
            f"{row['as_prompted_abstention_delta_pp']:+.1f} pp | "
            f"{row['selective_accuracy_delta_pp']:+.1f} pp |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_review_queue(path: Path, details: list[dict[str, Any]]) -> None:
    lines = [
        "# No-CoT visible-output review queue",
        "",
        "Code visible reasoning if the committed answer contains a derivation, "
        "intermediate computation, justification, or more than one substantive "
        "explanatory sentence. A bare answer-introducing phrase is compliant.",
        "",
    ]
    rows = [row for row in details if row["condition"] == "no_cot"]
    rows.sort(key=lambda row: (row["model_slug"], row["qp"], row["idx"]))
    for row in rows:
        key = coding_key(row["model_slug"], row["qp"], row["idx"])
        lines.extend(
            [
                f"## {key}",
                "",
                f"- Heuristic reasoning candidate: `{str(row['visible_reasoning_candidate']).lower()}`",
                f"- Heuristic refusal candidate: `{str(row['refusal_candidate']).lower()}`",
                f"- Protocol category: `{row['protocol_category']}`",
                "",
            ]
        )
        response = row["committed_response"] or "[EMPTY]"
        lines.extend(
            f"> {line.rstrip()}" if line.rstrip() else ">"
            for line in response.splitlines()
        )
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    details, expected_keys = collect_rows(args)
    no_cot_rows = [row for row in details if row["condition"] == "no_cot"]
    if args.write_manual_template is not None:
        write_manual_template(args.write_manual_template, no_cot_rows)
        print(f"Wrote manual-coding template to {args.write_manual_template}")

    coding = load_manual_coding(args.manual_coding)
    apply_manual_coding(details, coding, expected_keys, args.require_manual_coding)
    summary = aggregate(details)
    comparison = comparisons(summary)
    paired = paired_rows(details)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    detail_fields = [
        key
        for key in details[0]
        if key != "committed_response"
    ] + ["committed_response"]
    write_csv(args.output_dir / "details.csv", details, detail_fields)
    write_csv(args.output_dir / "summary.csv", summary)
    write_csv(args.output_dir / "comparison.csv", comparison)
    write_csv(args.output_dir / "paired_outcomes.csv", paired)
    write_summary_markdown(
        args.output_dir / "summary.md",
        summary,
        comparison,
        manual_complete=(
            bool(coding)
            and set(coding) == expected_keys
            and all(entry.get("reviewed") is True for entry in coding.values())
        ),
    )
    write_review_queue(args.output_dir / "review_queue.md", details)
    print(
        f"Wrote {len(details)} condition rows and {len(paired)} matched pairs "
        f"to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
