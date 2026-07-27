#!/usr/bin/env python3
"""Validate and summarize the GPT-5.6 Sol Omni-MATH sweep."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path


MODEL = "openai/gpt-5.6-sol"
EXPECTED_PROVIDER = "openai"
EXPECTED_REASONING = "high"
EXPECTED_MAX_TOKENS = 64_000
EXPECTED_SEED = 100


@dataclass(frozen=True)
class Cell:
    key: str
    label: str
    slug: str
    nano_slug: str


CELLS = (
    Cell("r100", r"$r_{100}$", "quant_1_0_-100", "quant_1_0_-100"),
    Cell("rabstain", r"$r_{\mathrm{abstain}}$", "quant_-1_10_-10", "quant_-1_10_-10"),
    Cell("qp6", "QP6", "QP6", "QP6"),
    Cell("qp7", "QP7", "QP7", "QP7"),
)


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def expected_indices(dataset_size: int, n: int) -> set[int]:
    indices = list(range(dataset_size))
    random.Random(EXPECTED_SEED).shuffle(indices)
    return set(indices[:n])


def _as_cost(value, *, field: str, cell: str) -> float:
    if value is None:
        raise ValueError(f"{cell}: missing {field}")
    try:
        cost = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{cell}: invalid {field}={value!r}") from exc
    if cost < 0:
        raise ValueError(f"{cell}: negative {field}={cost}")
    return cost


def validate_rows(
    rows: list[dict],
    *,
    cell: Cell,
    expected_n: int,
    expected_ids: set[int],
) -> None:
    if len(rows) != expected_n:
        raise ValueError(f"{cell.key}: expected {expected_n} rows, found {len(rows)}")
    actual_ids = [row.get("idx") for row in rows]
    if len(set(actual_ids)) != len(actual_ids):
        raise ValueError(f"{cell.key}: duplicate idx values")
    if set(actual_ids) != expected_ids:
        missing = sorted(expected_ids - set(actual_ids))
        extra = sorted(set(actual_ids) - expected_ids)
        raise ValueError(f"{cell.key}: wrong sample IDs; missing={missing}, extra={extra}")

    for row in rows:
        idx = row["idx"]
        prefix = f"{cell.key} idx={idx}"
        if row.get("request_provider") != "openrouter":
            raise ValueError(f"{prefix}: request_provider is not openrouter")
        if row.get("request_model") != MODEL:
            raise ValueError(f"{prefix}: request_model is not {MODEL}")
        if row.get("request_openrouter_provider") != EXPECTED_PROVIDER:
            raise ValueError(f"{prefix}: upstream provider was not pinned to openai")
        provider = str(row.get("openrouter_provider") or "").lower()
        if provider not in {"openai", "openai/standard"}:
            raise ValueError(f"{prefix}: selected provider is {provider!r}, expected OpenAI")
        if row.get("reasoning_effort") != EXPECTED_REASONING:
            raise ValueError(f"{prefix}: reasoning effort is not high")
        if row.get("temperature") is not None:
            raise ValueError(f"{prefix}: temperature was not omitted")
        if row.get("max_completion_tokens") != EXPECTED_MAX_TOKENS:
            raise ValueError(f"{prefix}: max token budget is not 64000")
        if row.get("dataset_seed") != EXPECTED_SEED:
            raise ValueError(f"{prefix}: dataset seed is not 100")
        if "gpt-5.6-sol" not in str(row.get("response_model") or ""):
            raise ValueError(f"{prefix}: unexpected response model {row.get('response_model')!r}")
        _as_cost(row.get("cost"), field="cost", cell=prefix)
        for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if not isinstance(row.get(field), int):
                raise ValueError(f"{prefix}: missing or invalid {field}")
        if row.get("finish_reason") in {"length", "max_tokens", "max_output_tokens"}:
            raise ValueError(f"{prefix}: response was truncated")


def _metrics_row(metrics: dict) -> tuple[int, int, int, int, int, float, float]:
    n = metrics["num_total"]
    correct = metrics["num_correct"]
    incorrect = metrics["num_incorrect_standard"] + metrics["num_incorrect_mixed"]
    abstained = metrics["num_abstained"]
    indeterminate = metrics["num_indeterminate"]
    accuracy = metrics["accuracy_of_attempted"]
    abstention_rate = 100 * abstained / n if n else 0.0
    return n, correct, incorrect, abstained, indeterminate, accuracy, abstention_rate


def write_pilot_cost_report(
    path: Path,
    rows_by_cell: dict[str, list[dict]],
    metrics_by_cell: dict[str, dict],
) -> None:
    lines = [
        "# GPT-5.6 Sol pilot cost estimate",
        "",
        "Pilot: 5 Omni-MATH questions per condition (20 calls total), "
        "OpenRouter model `openai/gpt-5.6-sol`, upstream `openai`, "
        "reasoning effort `high`, temperature omitted, max output 64,000 tokens, seed 100.",
        "",
        "| Condition | Calls | Input tokens | Output tokens | Reasoning tokens | Actual cost | Mean/call | Projected N=100 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    total_actual = 0.0
    total_projected = 0.0
    total_input = 0
    total_output = 0
    total_reasoning = 0
    for cell in CELLS:
        rows = rows_by_cell[cell.key]
        actual = sum(_as_cost(row["cost"], field="cost", cell=cell.key) for row in rows)
        mean = actual / len(rows)
        projected = mean * 100
        input_tokens = sum(row["prompt_tokens"] for row in rows)
        output_tokens = sum(row["completion_tokens"] for row in rows)
        reasoning_tokens = sum((row.get("reasoning_tokens") or 0) for row in rows)
        total_actual += actual
        total_projected += projected
        total_input += input_tokens
        total_output += output_tokens
        total_reasoning += reasoning_tokens
        lines.append(
            f"| {cell.label} | {len(rows)} | {input_tokens:,} | {output_tokens:,} | "
            f"{reasoning_tokens:,} | ${actual:.6f} | ${mean:.6f} | ${projected:.2f} |"
        )
    lines.extend([
        f"| **Total** | **20** | **{total_input:,}** | **{total_output:,}** | "
        f"**{total_reasoning:,}** | **${total_actual:.6f}** | — | **${total_projected:.2f}** |",
        "",
        f"Linear projection for the remaining 95 calls per condition: "
        f"**${max(total_projected - total_actual, 0):.2f}**. "
        "The projection uses exact per-request OpenRouter charges from this pilot; "
        "the realized cost can vary with response length.",
        "",
        "## Pilot outcomes",
        "",
        "| Condition | Correct | Incorrect | Abstained | Indeterminate | Attempted accuracy |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for cell in CELLS:
        _, correct, incorrect, abstained, indeterminate, accuracy, _ = _metrics_row(
            metrics_by_cell[cell.key]
        )
        lines.append(
            f"| {cell.label} | {correct} | {incorrect} | {abstained} | "
            f"{indeterminate} | {accuracy:.1f}% |"
        )
    lines.extend([
        "",
        "Pilot sample IDs (shared by all four conditions): "
        "`539, 903, 1464, 2279, 2637`.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_comparison_report(
    path: Path,
    metrics_by_cell: dict[str, dict],
    nano_metrics_by_cell: dict[str, dict],
    baseline_accuracy: float,
) -> None:
    lines = [
        "# GPT-5.6 Sol comparison on Omni-MATH",
        "",
        "GPT-5.6 Sol: OpenRouter `openai/gpt-5.6-sol`, upstream `openai`, "
        "reasoning effort `high`, temperature omitted, max output 64,000 tokens, seed 100, N=100.",
        "",
        "Prior GPT-5.4 Nano results use reasoning effort `medium`, T=1.0, "
        "max output 64,000 tokens, and seed 100.",
        "",
        "| Condition | Model | N | Correct | Incorrect | Abstained | Indeterminate | Attempted accuracy | Abstention rate |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    deltas = []
    for cell in CELLS:
        sol = _metrics_row(metrics_by_cell[cell.key])
        nano = _metrics_row(nano_metrics_by_cell[cell.key])
        for model_name, values in (("GPT-5.6 Sol", sol), ("GPT-5.4 Nano", nano)):
            n, correct, incorrect, abstained, indeterminate, accuracy, abstention_rate = values
            lines.append(
                f"| {cell.label} | {model_name} | {n} | {correct} | {incorrect} | "
                f"{abstained} | {indeterminate} | {accuracy:.1f}% | {abstention_rate:.1f}% |"
            )
        deltas.append((cell.label, sol[5] - nano[5], sol[6] - nano[6]))
    lines.extend([
        "",
        "## GPT-5.6 Sol selective accuracy minus no-consequence baseline",
        "",
        f"The GPT-5.6 Sol `standard` no-consequence baseline accuracy is "
        f"**{baseline_accuracy:.1f}%** over the same 100 questions. Following the "
        "paper's convention, Δ is attempted (selective) accuracy minus this overall "
        "baseline accuracy.",
        "",
        "| Condition | Attempted accuracy | Δ vs Sol baseline |",
        "|---|---:|---:|",
    ])
    for cell in CELLS:
        accuracy = _metrics_row(metrics_by_cell[cell.key])[5]
        lines.append(f"| {cell.label} | {accuracy:.1f}% | {accuracy - baseline_accuracy:+.1f} pp |")
    lines.extend([
        "",
        "## GPT-5.6 Sol minus GPT-5.4 Nano",
        "",
        "| Condition | Δ attempted accuracy | Δ abstention rate |",
        "|---|---:|---:|",
    ])
    for label, accuracy_delta, abstention_delta in deltas:
        lines.append(f"| {label} | {accuracy_delta:+.1f} pp | {abstention_delta:+.1f} pp |")
    lines.extend([
        "",
        "Note: the stored prior QP6 GPT-5.4 Nano metrics contain N=99; all other "
        "prior cells and every GPT-5.6 Sol cell contain N=100.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def summarize(repo_root: Path, num_samples: int) -> Path:
    if num_samples not in (5, 100):
        raise ValueError("num_samples must be 5 (pilot) or 100 (full)")

    dataset_size = len(read_jsonl(repo_root / "omni_math_rule.jsonl"))
    ids = expected_indices(dataset_size, num_samples)
    result_root = repo_root / "inference/results/qualitative_quantitative_sweep"
    eval_root = repo_root / "evaluation/output/qualitative_quantitative_sweep"
    rows_by_cell: dict[str, list[dict]] = {}
    metrics_by_cell: dict[str, dict] = {}

    for cell in CELLS:
        rows = read_jsonl(result_root / f"gpt-5.6-sol_{cell.slug}.jsonl")
        validate_rows(
            rows,
            cell=cell,
            expected_n=num_samples,
            expected_ids=ids,
        )
        metrics = read_json(eval_root / f"gpt-5.6-sol_{cell.slug}/cautious_metrics.json")
        if metrics.get("num_total") != num_samples:
            raise ValueError(
                f"{cell.key}: evaluator has N={metrics.get('num_total')}, expected {num_samples}"
            )
        rows_by_cell[cell.key] = rows
        metrics_by_cell[cell.key] = metrics

    if num_samples == 5:
        output = eval_root / "gpt-5.6-sol-pilot-cost.md"
        write_pilot_cost_report(output, rows_by_cell, metrics_by_cell)
    else:
        nano_metrics = {
            cell.key: read_json(
                eval_root / f"gpt-5.4-nano_{cell.nano_slug}/cautious_metrics.json"
            )
            for cell in CELLS
        }
        baseline_metrics = read_json(
            repo_root
            / "evaluation/output/baselines/gpt-5.6-sol/omni-math/math_eval_cot_metrics.json"
        )
        if baseline_metrics.get("num_samples") != 100:
            raise ValueError("GPT-5.6 Sol baseline does not contain N=100")
        output = eval_root / "gpt-5.6-sol-comparison.md"
        write_comparison_report(
            output,
            metrics_by_cell,
            nano_metrics,
            float(baseline_metrics["acc"]),
        )
    print(f"Validated all four cells and wrote {output}")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--num-samples", type=int, required=True, choices=(5, 100))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    summarize(args.repo_root.resolve(), args.num_samples)
