#!/usr/bin/env python3
"""Consolidate the per-(method, prompt) abstention-eval markdown tables in
evaluation/output/abstention_ft/ into a single clean markdown report.

Reads files named {gemma|qwen35}_{method}_{prompt}.md (qwen files carry an
extra "summary" token), parses their pipe tables, and emits tables grouped by
(model, training method, train-dataset abstention %). A Framing column keeps
the per-prompt rows distinct; Normalized Utility is computed for the quantitative
framings as (correct - penalty*incorrect)/total and left blank for QP* prompts.
"""
import glob
import os

INPUT_DIR = "evaluation/output/abstention_ft"
OUTPUT_MD = "evaluation/output/abstention_ft/combined_abstention_summary.md"

MODEL_DISPLAY = {"gemma4_e2b": "Gemma 4 E2B", "qwen35_9b": "Qwen3.5-9B"}
METHOD_DISPLAY = {"dpo": "DPO", "sft_box": "SFT-Box", "sft": "SFT"}
FRAMING_ORDER = ["quant_m0_25", "quant_m1", "quant_m5", "quant_m25", "quant_m100",
                 "QP1", "QP4", "QP7"]
FRAMING_RANK = {f: i for i, f in enumerate(FRAMING_ORDER)}
QUANT_PENALTY = {"quant_m0_25": 0.25, "quant_m1": 1, "quant_m5": 5,
                 "quant_m25": 25, "quant_m100": 100}


def epoch_from_slug(slug: str) -> float:
    # ..._ep0p25 / _ep0p5 / _ep1 / _ep4  ->  0.25 / 0.5 / 1 / 4
    tag = slug.rsplit("_ep", 1)[1]
    return float(tag.replace("p", "."))


def fmt_epoch(e: float) -> str:
    return f"{e:g}"


def fmt_pct(x):
    return f"{x * 100:.1f}%" if x is not None else "—"


def parse_md_table(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip()]
    if not lines:
        return rows
    header = [c.strip() for c in lines[0].strip("|").split("|")]
    idx = {name: i for i, name in enumerate(header)}
    for ln in lines[2:]:  # skip header + separator
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) != len(header):
            continue
        rows.append({name: cells[idx[name]] for name in header})
    return rows


def to_int(v):
    return int(v) if v not in (None, "", "None") else None


def to_float(v):
    return float(v) if v not in (None, "", "None") else None


def main():
    records = []
    for path in glob.glob(os.path.join(INPUT_DIR, "*.md")):
        base = os.path.basename(path)
        if base == os.path.basename(OUTPUT_MD):
            continue
        for r in parse_md_table(path):
            slug = r.get("variant_slug", "")
            model = r.get("base_family")
            method = r.get("method")
            if model not in MODEL_DISPLAY or "_ep" not in slug:
                continue
            correct = to_int(r.get("correct"))
            incorrect = to_int(r.get("incorrect"))
            abstained = to_int(r.get("abstained"))
            total = to_int(r.get("total")) or 100
            prompt = r.get("prompt")
            norm_util = None
            if prompt in QUANT_PENALTY and correct is not None and incorrect is not None:
                norm_util = (correct - QUANT_PENALTY[prompt] * incorrect) / total
            records.append({
                "model": model,
                "method": method,
                "abst_pct": to_int(r.get("abstention_pct")),
                "epoch": epoch_from_slug(slug),
                "framing": prompt,
                "correct": correct,
                "incorrect": incorrect,
                "abstained": abstained,
                "abstention_rate": to_float(r.get("abstention_rate")),
                "selective_accuracy": to_float(r.get("attempted_accuracy")),
                "norm_utility": norm_util,
            })

    # Group by (model, method, abst_pct).
    groups = {}
    for rec in records:
        groups.setdefault((rec["model"], rec["method"], rec["abst_pct"]), []).append(rec)

    def model_rank(m):
        return list(MODEL_DISPLAY).index(m)

    def method_rank(m):
        order = ["sft", "sft_box", "dpo"]
        return order.index(m) if m in order else len(order)

    cols = ["Model", "Training method", "Train abst %", "Epoch", "Framing",
            "Correct", "Incorrect", "Abstained", "Abstention Rate",
            "Selective Accuracy", "Normalized Utility"]

    out = ["# Abstention Fine-Tuning — Consolidated Eval Summary", ""]
    out.append("Tables grouped by (model, training method, train-dataset abstention %). "
               "Each row is a (framing × epoch) eval cell. Normalized Utility = "
               "`(correct − penalty × incorrect) / total` for quantitative framings "
               "(penalty 0.25/1/5/25/100); left blank for qualitative QP framings.")
    out.append("")

    for key in sorted(groups, key=lambda k: (model_rank(k[0]), method_rank(k[1]), k[2])):
        model, method, abst_pct = key
        recs = sorted(groups[key], key=lambda r: (FRAMING_RANK.get(r["framing"], 99), r["epoch"]))
        out.append(f"## {MODEL_DISPLAY[model]} · {METHOD_DISPLAY.get(method, method)} · "
                   f"train abstention {abst_pct}%")
        out.append("")
        out.append("| " + " | ".join(cols) + " |")
        out.append("| " + " | ".join(["---"] * len(cols)) + " |")
        for r in recs:
            nu = f"{r['norm_utility']:.2f}" if r["norm_utility"] is not None else "—"
            out.append("| " + " | ".join([
                MODEL_DISPLAY[model],
                METHOD_DISPLAY.get(method, method),
                f"{abst_pct}%",
                fmt_epoch(r["epoch"]),
                r["framing"],
                str(r["correct"]),
                str(r["incorrect"]),
                str(r["abstained"]),
                fmt_pct(r["abstention_rate"]),
                fmt_pct(r["selective_accuracy"]),
                nu,
            ]) + " |")
        out.append("")

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"wrote {OUTPUT_MD} ({len(records)} rows, {len(groups)} tables)")


if __name__ == "__main__":
    main()
