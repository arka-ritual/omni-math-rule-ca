#!/usr/bin/env python3
"""Side-by-side comparison: instruct vs base × few-shot variant.

Reads `cautious_metrics.json` from four flavours of result directory under
`evaluation/output/`:

  * `<instruct_slug>-<prompt>`                   instruct, no fewshot
  * `<instruct_slug>-<prompt>_fs-<variant>`      instruct + fewshot
  * `<base_slug>-<prompt>`                       base,     no fewshot
  * `<base_slug>-<prompt>_basemodel_fs-<variant>` base + fewshot

and emits a markdown table per prompt with two key signals:

  * abstention_rate (fraction of total problems where the model produced
    `\\boxed{UNSURE}`, the `Answer/Abstain decision: ABSTAIN` marker, or
    no `\\boxed{}` at all in a non-truncated response)
  * selective_accuracy (correct / (correct + incorrect) — i.e. accuracy
    on the *attempted* subset, excluding both abstained and indeterminate)

Missing cells are rendered as "—" so partial runs still produce a usable
table.

Usage:
    python scripts/compare_fewshot_instruct_vs_base.py \
        --prompts ultra_cautious QP4 \
        --variants normal no_conseq conseq_correct_abstain \
        --instruct_slug gemma-4-E2B-it \
        --base_slug gemma-4-E2B \
        --output_md evaluation/output/gemma-4-E2B-it-fewshot_vs_base.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional


def read_metrics(path: str) -> Optional[dict]:
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def cell_summary(metrics: Optional[dict]) -> tuple[Optional[float], Optional[float], Optional[int]]:
    """Returns (abstention_rate, selective_accuracy, n_total)."""
    if metrics is None:
        return None, None, None
    n_total = metrics.get("num_total")
    n_abst  = metrics.get("num_abstained", 0)
    n_indet = metrics.get("num_indeterminate", 0)
    # The legacy main-branch metrics emitted num_incorrect_length_cut instead
    # of num_indeterminate; treat it as the same bucket.
    if "num_incorrect_length_cut" in metrics:
        n_indet = max(n_indet, metrics["num_incorrect_length_cut"])
    n_corr  = metrics.get("num_correct", 0)
    n_inc   = sum(metrics.get(k, 0) for k in [
        "num_incorrect_standard", "num_incorrect_mixed", "num_incorrect_length_cut",
    ])
    abst_rate = (n_abst / n_total) if n_total else None
    attempted = n_corr + n_inc
    sel_acc = (n_corr / attempted) if attempted else None
    return abst_rate, sel_acc, n_total


def fmt_pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{100 * x:.1f}%"


def fmt_n(x: Optional[int]) -> str:
    return "—" if x is None else str(x)


def metric_path(eval_root: str, exp_name: str) -> str:
    return os.path.join(eval_root, exp_name, "omni-math", "cautious_metrics.json")


def build_table(
    prompts: list[str],
    variants: list[str],
    instruct_slug: str,
    base_slug: str,
    eval_root: str,
) -> str:
    lines: list[str] = []
    for prompt in prompts:
        lines.append(f"## Prompt: `{prompt}`")
        lines.append("")
        lines.append(
            "| Row | Instruct abst | Instruct sel.acc (n) | Base abst | Base sel.acc (n) |"
        )
        lines.append(
            "|---|---|---|---|---|"
        )

        # --- Row 1: no-fewshot baselines ---
        inst_m = read_metrics(metric_path(eval_root, f"{instruct_slug}-{prompt}"))
        base_m = read_metrics(metric_path(eval_root, f"{base_slug}-{prompt}"))
        i_abst, i_sel, i_n = cell_summary(inst_m)
        b_abst, b_sel, b_n = cell_summary(base_m)
        lines.append(
            f"| **no-fewshot** | {fmt_pct(i_abst)} | {fmt_pct(i_sel)} ({fmt_n(i_n)}) | "
            f"{fmt_pct(b_abst)} | {fmt_pct(b_sel)} ({fmt_n(b_n)}) |"
        )

        # --- Rows 2..k: per-variant ---
        for variant in variants:
            inst_exp = f"{instruct_slug}-{prompt}_fs-{variant}"
            base_exp = f"{base_slug}-{prompt}_basemodel_fs-{variant}"
            inst_m = read_metrics(metric_path(eval_root, inst_exp))
            base_m = read_metrics(metric_path(eval_root, base_exp))
            i_abst, i_sel, i_n = cell_summary(inst_m)
            b_abst, b_sel, b_n = cell_summary(base_m)
            lines.append(
                f"| fewshot=`{variant}` | {fmt_pct(i_abst)} | {fmt_pct(i_sel)} ({fmt_n(i_n)}) | "
                f"{fmt_pct(b_abst)} | {fmt_pct(b_sel)} ({fmt_n(b_n)}) |"
            )
        lines.append("")
        # Footnote about delta — only printed if both baselines are present.
        if inst_m_no_fs := read_metrics(metric_path(eval_root, f"{instruct_slug}-{prompt}")):
            base_abst_no_fs, _, _ = cell_summary(read_metrics(metric_path(eval_root, f"{base_slug}-{prompt}")))
            inst_abst_no_fs, _, _ = cell_summary(inst_m_no_fs)
            lines.append(
                f"*no-fewshot abstention: instruct={fmt_pct(inst_abst_no_fs)}, "
                f"base={fmt_pct(base_abst_no_fs)}*"
            )
            lines.append("")

    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prompts", nargs="+", required=True,
                   help="Prompt presets to include (e.g. ultra_cautious QP4 QP7)")
    p.add_argument("--variants", nargs="+", required=True,
                   help="Few-shot variants to include (e.g. normal no_conseq conseq_correct_abstain)")
    p.add_argument("--instruct_slug", required=True,
                   help='Instruct-model slug used in result directory names (e.g. "gemma-4-E2B-it")')
    p.add_argument("--base_slug", required=True,
                   help='Base-model slug used in result directory names (e.g. "gemma-4-E2B")')
    p.add_argument("--eval_root", default="evaluation/output",
                   help="Root directory containing per-experiment result subdirs")
    p.add_argument("--output_md", default=None,
                   help="If set, write the table to this path. Always also printed to stdout.")
    args = p.parse_args()

    table = build_table(
        prompts=args.prompts,
        variants=args.variants,
        instruct_slug=args.instruct_slug,
        base_slug=args.base_slug,
        eval_root=args.eval_root,
    )

    header = (
        f"# Few-shot preamble: instruct ({args.instruct_slug}) vs base ({args.base_slug})\n\n"
        "Per-row: abstention rate (fraction of all problems where the model produced "
        "`\\boxed{UNSURE}` or no `\\boxed{}` in a non-truncated response) and "
        "selective accuracy on the *attempted* subset (correct / (correct + incorrect))."
        "\n\n"
    )
    full = header + table

    print(full)
    if args.output_md:
        os.makedirs(os.path.dirname(args.output_md) or ".", exist_ok=True)
        with open(args.output_md, "w", encoding="utf-8") as f:
            f.write(full)
        print(f"\n[wrote] {args.output_md}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
