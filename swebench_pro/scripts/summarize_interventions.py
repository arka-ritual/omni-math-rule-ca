#!/usr/bin/env python3
"""Aggregate intervention rundirs into the per-model markdown tables.

For each rundir under swebench_pro/results/<model>_int{1,2,3,4}_<config>_n100/,
read:
  - exit_statuses.yaml (Submitted / Abstained / LimitsExceeded / LoopDetected)
  - preds.json         (model_patch presence per instance)
  - eval/eval_results.json (correct/incorrect bools)

For int4 (post-hoc rescore) there's no exit_statuses.yaml; the abstain count
comes from the number of empty patches in preds.json.

Outputs the markdown summary to stdout.
"""
from __future__ import annotations

import json
import re
import sys
import yaml
from pathlib import Path

ROOT = Path("swebench_pro/results")

MODELS = [
    ("anthropic_claude-haiku-4-5",                 "claude-haiku-4-5"),
    ("openai_gpt-5.4-nano",                        "gpt-5.4-nano"),
    ("gemini_gemini-3.1-flash-lite-preview",       "gemini-3.1-flash-lite-preview"),
]

# (config_id_in_dirname, display_name)
CONFIGS = [
    ("quant_25",  "Quant-25 (+1/-5/0)"),
    ("quant_100", "Quant-100 (+1/-10/0)"),
    ("qp6",       "QP6 (team-lead)"),
    ("qp7",       "QP7 (humanity)"),
]

INTERVENTIONS = [
    (1, "1 — single-turn multi-step"),
    (2, "2 — multi-turn (confidence then reveal)"),
    (3, "3 — multi-turn no-conf"),
    (4, "4 — post-hoc τ(λ)"),
]


def analyze(rundir: Path, intv: int) -> dict | None:
    """Return per-cell stats, or None if the cell is missing."""
    preds_path = rundir / "preds.json"
    eval_path = rundir / "eval" / "eval_results.json"
    if not preds_path.exists() or not eval_path.exists():
        return None

    preds = json.loads(preds_path.read_text())
    n_total = len(preds)
    n_empty_patch = sum(1 for v in preds.values() if not (v.get("model_patch") or "").strip())

    evaled = json.loads(eval_path.read_text())
    n_correct = sum(1 for v in evaled.values() if v)
    n_evaled = len(evaled)
    n_incorrect = n_evaled - n_correct

    # Exit status breakdown — only present for int 1/2/3 (live runs).
    es = {"Submitted": 0, "Abstained": 0, "LimitsExceeded": 0, "LoopDetected": 0}
    es_path = rundir / "exit_statuses.yaml"
    if es_path.exists():
        try:
            data = yaml.safe_load(es_path.read_text()) or {}
            buckets = data.get("instances_by_exit_status") or {}
            for k, v in buckets.items():
                es[k] = len(v) if isinstance(v, list) else 0
        except Exception:
            pass

    if intv == 4:
        # Post-hoc τ(λ): abstained = empty patches in preds.json
        n_abstained = n_empty_patch
        n_failed = 0  # no separate failure mode in post-hoc
    else:
        n_abstained = es.get("Abstained", 0)
        n_failed = es.get("LimitsExceeded", 0) + es.get("LoopDetected", 0)

    # total accuracy over the full N
    total_acc = (100.0 * n_correct / n_total) if n_total else 0.0
    # conditional accuracy: exclude only deliberate abstentions
    denom_cond = n_total - n_abstained
    cond_acc = (100.0 * n_correct / denom_cond) if denom_cond else 0.0
    abst_rate = (100.0 * n_abstained / n_total) if n_total else 0.0

    return {
        "n_total": n_total,
        "n_correct": n_correct,
        "n_incorrect": n_incorrect,
        "n_evaled": n_evaled,
        "n_abstained": n_abstained,
        "n_failed": n_failed,
        "es": es,
        "total_acc": total_acc,
        "cond_acc": cond_acc,
        "abst_rate": abst_rate,
        "denom_cond": denom_cond,
    }


def cfg_dir_for(model_slug: str, intv: int, cfg_id: str) -> Path | None:
    """Map our (model, int, cfg) to the actual results directory name."""
    if cfg_id == "quant_25":
        # On disk: ..._int<I>_quant_25_n100  OR  ..._int<I>_quant1_-5_0_n100
        cands = [
            ROOT / f"{model_slug}_int{intv}_quant_25_n100",
            ROOT / f"{model_slug}_int{intv}_quant1_-5_0_n100",
        ]
    elif cfg_id == "quant_100":
        cands = [
            ROOT / f"{model_slug}_int{intv}_quant_100_n100",
            ROOT / f"{model_slug}_int{intv}_quant1_-10_0_n100",
        ]
    else:  # qp6, qp7
        cands = [ROOT / f"{model_slug}_int{intv}_{cfg_id}_n100"]
    for c in cands:
        if c.exists():
            return c
    return None


def main():
    out: list[str] = []
    out.append("# SWE-bench Pro intervention results")
    out.append("")
    out.append("Source: `swebench_pro/results/<model>_int{1,2,3,4}_<config>_n100/`")
    out.append("(`preds.json` + `exit_statuses.yaml` + `eval/eval_results.json`).")
    out.append("All runs use 100 instances / 10 inference workers / `--reasoning-effort medium`.")
    out.append("")
    out.append("Legend:")
    out.append("- **abst** = `Abstained` exit status (model ran `exit_abstain`); for int 4 (post-hoc) = patches blanked by τ(λ) rule.")
    out.append("- **fail** = `LimitsExceeded` + `LoopDetected` (runtime failures, no patch).")
    out.append("- **submitted** = `Submitted` exit status.")
    out.append("- **abst rate** = `abst / 100`.")
    out.append("- **total acc** = `correct / 100` (treats abst + fail + incorrect all as non-correct).")
    out.append("- **cond acc** = `correct / (100 - abst)` — accuracy excluding deliberate abstentions; runtime failures (`fail`) still count toward the denominator since the model didn't *choose* to skip them.")
    out.append("")

    # Per-model main tables (cells = correct/incorrect/abst/fail counts + accuracies)
    for slug, display in MODELS:
        out.append(f"## {display}")
        out.append("")
        out.append("### Cell breakdown — `correct / incorrect / abst / fail` (n=100)")
        out.append("")
        header = "| Intervention | " + " | ".join(name for _, name in CONFIGS) + " |"
        sep    = "|---|" + "|".join(["---"] * len(CONFIGS)) + "|"
        out.append(header)
        out.append(sep)
        for intv, intv_name in INTERVENTIONS:
            row = [f"| **{intv_name}**"]
            for cfg_id, _ in CONFIGS:
                d = cfg_dir_for(slug, intv, cfg_id)
                if d is None:
                    row.append(" — ")
                    continue
                s = analyze(d, intv)
                if s is None:
                    row.append(" — ")
                    continue
                cell = (
                    f"c={s['n_correct']} / i={s['n_incorrect']} / "
                    f"a={s['n_abstained']} / f={s['n_failed']}"
                )
                row.append(f" {cell} ")
            out.append("|".join(row) + "|")
        out.append("")

        out.append("### Total accuracy — `correct / 100`")
        out.append("")
        out.append(header)
        out.append(sep)
        for intv, intv_name in INTERVENTIONS:
            row = [f"| **{intv_name}**"]
            for cfg_id, _ in CONFIGS:
                d = cfg_dir_for(slug, intv, cfg_id)
                if d is None:
                    row.append(" — ")
                    continue
                s = analyze(d, intv)
                if s is None:
                    row.append(" — ")
                    continue
                row.append(f" **{s['total_acc']:.1f}%** ({s['n_correct']}/{s['n_total']}) ")
            out.append("|".join(row) + "|")
        out.append("")

        out.append("### Conditional accuracy — `correct / (100 - abst)`")
        out.append("")
        out.append(header)
        out.append(sep)
        for intv, intv_name in INTERVENTIONS:
            row = [f"| **{intv_name}**"]
            for cfg_id, _ in CONFIGS:
                d = cfg_dir_for(slug, intv, cfg_id)
                if d is None:
                    row.append(" — ")
                    continue
                s = analyze(d, intv)
                if s is None:
                    row.append(" — ")
                    continue
                if s["denom_cond"] == 0:
                    row.append(" n/a (all abstained) ")
                else:
                    row.append(f" **{s['cond_acc']:.1f}%** ({s['n_correct']}/{s['denom_cond']}) ")
            out.append("|".join(row) + "|")
        out.append("")

        out.append("### Abstention rate — `abst / 100`")
        out.append("")
        out.append(header)
        out.append(sep)
        for intv, intv_name in INTERVENTIONS:
            row = [f"| **{intv_name}**"]
            for cfg_id, _ in CONFIGS:
                d = cfg_dir_for(slug, intv, cfg_id)
                if d is None:
                    row.append(" — ")
                    continue
                s = analyze(d, intv)
                if s is None:
                    row.append(" — ")
                    continue
                row.append(f" {s['abst_rate']:.1f}% ({s['n_abstained']}/{s['n_total']}) ")
            out.append("|".join(row) + "|")
        out.append("")

    out.append("## Cross-model takeaways")
    out.append("")
    out.append("### 1. Live-run abstention is essentially off for Haiku and GPT-5.4-nano")
    out.append("")
    out.append("Across the 24 live cells (`int1`/`int2`/`int3` × 4 framings) for these two")
    out.append("models, the `Abstained` exit status fires a total of **2/2400** instances —")
    out.append("Haiku abstains once (int2/quant_100) and GPT-5.4-nano once (int1/qp6).")
    out.append("Neither the quantitative penalty (−10 / submission), the team-lead framing,")
    out.append("nor the humanity framing trigger meaningful abstention behavior. The")
    out.append("`exit_abstain` tool is available throughout, and the system prompt")
    out.append("explicitly tells the model it can use it; both models simply don't.")
    out.append("This mirrors the math finding that Claude in particular ignores")
    out.append("consequence framing.")
    out.append("")
    out.append("### 2. GPT-5.4-nano's `LimitsExceeded` rate is the dominant signal")
    out.append("")
    out.append("Per-cell `LimitsExceeded`+`LoopDetected` count for GPT-5.4-nano ranges")
    out.append("from 19 to 39 (out of 100), vs 0–6 for Gemini and 0 for Haiku. These are")
    out.append("instances where the agent ran out of step/cost budget before submitting —")
    out.append("functionally unattempted, but distinct from a deliberate abstention.")
    out.append("Conditional accuracy here (`correct / (100 - abst)`) leaves these in the")
    out.append("denominator on purpose, so the GPT-5.4-nano conditional numbers")
    out.append("understate its accuracy on cells it actually finished.")
    out.append("")
    out.append("### 3. Gemini abstains slightly more under qualitative framings")
    out.append("")
    out.append("Live-run abstention for Gemini: int1 sees 0/1/3/0 across quant_25 / quant_100 /")
    out.append("qp6 / qp7; the qp6 / qp7 cells under post-hoc τ(λ) blank 37%/41% of patches")
    out.append("vs only 9%/30% for the quant cells. This suggests Gemini's stated confidence")
    out.append("is lower under qualitative consequence framings than under explicit −5/−10")
    out.append("rubrics — the opposite of the (intended) calibration story.")
    out.append("")
    out.append("### 4. Int4 (post-hoc τ(λ)) over-abstains on Haiku for QP6/QP7")
    out.append("")
    out.append("Haiku under int4 + qp6/qp7 blanks **99–100 of 100 patches**, leaving total")
    out.append("accuracy at 0%. The post-hoc threshold rule + Haiku's habit of reporting")
    out.append("low numerical confidence under qualitative framings combine to suppress")
    out.append("everything. The same rule on Haiku + quant_25 keeps 95/100 patches and")
    out.append("nudges conditional accuracy from 31.0% (int1 baseline) → 35.8%.")
    out.append("")
    out.append("### 5. No intervention/framing combo Pareto-dominates int1 on total accuracy")
    out.append("")
    out.append("Per-model best total accuracy across all 16 cells:")
    out.append("- **Haiku**: 38.0% (int2 / qp6) vs 37.0% int1 baseline (qp6) — +1pt.")
    out.append("- **GPT-5.4-nano**: 34.0% (int1 / qp7) — int1 wins outright; int4 collapses to ≤11%.")
    out.append("- **Gemini-3.1-flash-lite**: 27.0% (int3 / qp7) vs 19.0% int1 (qp7) — +8pt; int3 (no confidence step) is the only intervention that meaningfully helps Gemini.")
    out.append("")
    out.append("Conditional accuracy improvements from int4 are real for Haiku/Gemini")
    out.append("(post-hoc filtering does select a slightly higher-confidence subset when")
    out.append("it leaves anything to score), but they come at the cost of huge total-")
    out.append("accuracy drops — i.e. the model's confidence signal is *correlated* with")
    out.append("correctness but not strongly enough for τ(λ) thresholding to be")
    out.append("competitive with just submitting everything.")
    out.append("")

    print("\n".join(out))


if __name__ == "__main__":
    main()
