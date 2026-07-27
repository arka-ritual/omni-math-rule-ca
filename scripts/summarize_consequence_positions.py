#!/usr/bin/env python3
"""Aggregate cautious-evaluation metrics for the position ablation."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


MODELS = {
    "claude-haiku-4-5": "Claude Haiku 4.5",
    "deepseek-v4-pro": "DeepSeek V4 Pro",
    "gemini-3.1-flash-lite": "Gemini 3.1 Flash Lite",
    "gpt-5.4-nano": "GPT-5.4 Nano",
    "qwen3.5-397b-a17b": "Qwen3.5 397B A17B",
}
QPS = ("QP6", "QP7")
POSITIONS = ("original", "beginning", "end")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--eval-dir",
        type=Path,
        default=Path("evaluation/output/consequence_position"),
    )
    parser.add_argument("--output-markdown", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--model", choices=MODELS)
    parser.add_argument("--qp", choices=QPS)
    parser.add_argument("--position", choices=POSITIONS)
    return parser.parse_args()


def collect(args: argparse.Namespace) -> list[dict[str, object]]:
    model_slugs = (args.model,) if args.model else tuple(MODELS)
    qps = (args.qp,) if args.qp else QPS
    positions = (args.position,) if args.position else POSITIONS
    rows: list[dict[str, object]] = []
    missing: list[Path] = []
    for slug in model_slugs:
        for qp in qps:
            for position in positions:
                metrics_path = (
                    args.eval_dir
                    / f"{slug}_{qp}_{position}"
                    / "cautious_metrics.json"
                )
                if not metrics_path.exists():
                    missing.append(metrics_path)
                    continue
                metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
                total = int(metrics["num_total"])
                abstained = int(metrics["num_abstained"])
                rows.append(
                    {
                        "model": MODELS[slug],
                        "model_slug": slug,
                        "qp": qp,
                        "position": position,
                        "total": total,
                        "abstained": abstained,
                        "abstention_rate": round(100 * abstained / total, 1)
                        if total
                        else 0.0,
                        "indeterminate": int(metrics["num_indeterminate"]),
                        "answered": int(metrics["num_attempted"]),
                        "correct": int(metrics["num_correct"]),
                        "selective_accuracy": float(
                            metrics["accuracy_of_attempted"]
                        ),
                    }
                )
    if missing:
        formatted = "\n".join(f"  {path}" for path in missing)
        raise SystemExit(f"Missing {len(missing)} expected metrics file(s):\n{formatted}")
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, object]]) -> None:
    lines = [
        "| Model | QP | Consequence position | N | Abstained | "
        "Abstention rate | Indeterminate | Answered | Correct | "
        "Selective accuracy |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['model']} | {row['qp']} | {row['position']} | "
            f"{row['total']} | {row['abstained']} | "
            f"{row['abstention_rate']:.1f}% | {row['indeterminate']} | "
            f"{row['answered']} | {row['correct']} | "
            f"{row['selective_accuracy']:.1f}% |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    rows = collect(args)
    if not rows:
        raise SystemExit("No metrics matched the requested filters")
    write_csv(args.output_csv, rows)
    write_markdown(args.output_markdown, rows)
    print(f"Wrote {len(rows)} rows to {args.output_markdown} and {args.output_csv}")


if __name__ == "__main__":
    main()
