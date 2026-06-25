#!/usr/bin/env python3
"""Plot the HLE (Humanity's Last Exam, Humanities/Social Science) OOD eval.

Reads cautious-eval metrics directly from evaluation/output/abstention_ft_hle/
{variant}__{prompt}/cautious_metrics.json (produced by inference/run_hle_ood.sh)
and renders, per (model, method), the same three views as the in-distribution
summary plots:
  A. train abstention 50% -> metric vs epochs   (one line per framing)
  B. epoch 1              -> metric vs train-dataset abstention %  (one line per framing)
  C. train abstention 50%, epoch 1 -> metric across framings (in-dist quant_m25 vs OOD)
The original (untrained) model is drawn as a dashed baseline where available.

Metrics: abstention rate (= num_abstained/num_total), selective accuracy
(= accuracy_of_attempted), normalized utility (quant framings only).

NOTE: HLE exact-match answers are graded with math_equal, so selective accuracy
on the exact-match subset is a rule-based lower bound; abstention rate is exact.

Usage:  python scripts/plot_hle.py
"""
import glob
import json
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INPUT_DIR = "evaluation/output/abstention_ft_hle"
OUT_DIR = "evaluation/output/abstention_ft_hle/plots"

MODEL_DISPLAY = {"gemma4_e2b": "Gemma 4 E2B", "qwen35_9b": "Qwen3.5-9B"}
METHOD_DISPLAY = {"sft_box": "SFT-Box", "dpo": "DPO", "sft": "SFT"}
FRAMING_ORDER = ["quant_m0_25", "quant_m1", "quant_m5", "quant_m25", "quant_m100",
                 "QP1", "QP4", "QP7"]
QUANT_FRAMINGS = ["quant_m0_25", "quant_m1", "quant_m5", "quant_m25", "quant_m100"]
QUANT_PENALTY = {"quant_m0_25": 0.25, "quant_m1": 1, "quant_m5": 5,
                 "quant_m25": 25, "quant_m100": 100}
FRAMING_COLOR = {
    "quant_m0_25": "#17becf", "quant_m1": "#7f7f7f", "quant_m5": "#1f77b4",
    "quant_m25": "#d62728", "quant_m100": "#2ca02c",
    "QP1": "#9467bd", "QP4": "#ff7f0e", "QP7": "#8c564b",
}
P_COLOR = {10: "#1f77b4", 25: "#ff7f0e", 50: "#2ca02c", 75: "#d62728", 90: "#9467bd"}
IN_DIST = "quant_m25"

CKPT_RE = re.compile(
    r"^(?P<model>gemma4_e2b|qwen35_9b)_qlora_(?P<method>\w+?)"
    r"_n500_quant_m25_k512_p(?P<p>\d+)_ep(?P<ep>[0-9p]+)__(?P<prompt>.+)$"
)
ORIG_RE = re.compile(r"^(?P<model>gemma4_e2b|qwen35_9b)_original__(?P<prompt>.+)$")

METRICS = {
    "abstention_rate": ("Abstention rate", (0, 1)),
    "selective_accuracy": ("Selective accuracy", (0, 1)),
    "utility": ("Normalized utility", None),
}


def read_metrics(cell_dir):
    path = os.path.join(cell_dir, "cautious_metrics.json")
    if not os.path.exists(path):
        return None
    m = json.load(open(path))
    total = m.get("num_total") or 0
    if not total:
        return None
    correct = m.get("num_correct", 0)
    abstained = m.get("num_abstained", 0)
    incorrect = m.get("num_incorrect_standard", 0) + m.get("num_incorrect_mixed", 0)
    sel = m.get("accuracy_of_attempted")
    sel = sel / 100 if sel is not None else None
    return {"total": total, "correct": correct, "incorrect": incorrect,
            "abstained": abstained, "abstention_rate": abstained / total,
            "selective_accuracy": sel}


def util_for(prompt, met):
    if prompt in QUANT_PENALTY and met:
        return (met["correct"] - QUANT_PENALTY[prompt] * met["incorrect"]) / met["total"]
    return None


def load():
    ckpts, origs = [], {}
    for d in sorted(glob.glob(os.path.join(INPUT_DIR, "*__*"))):
        if not os.path.isdir(d):
            continue
        name = os.path.basename(d)
        met = read_metrics(d)
        if met is None:
            continue
        mo = ORIG_RE.match(name)
        if mo:
            origs.setdefault(mo["model"], {})[mo["prompt"]] = {
                **met, "utility": util_for(mo["prompt"], met)}
            continue
        mc = CKPT_RE.match(name)
        if not mc:
            continue
        ckpts.append({
            "model": mc["model"], "method": mc["method"], "p": int(mc["p"]),
            "epoch": float(mc["ep"].replace("p", ".")), "framing": mc["prompt"],
            "utility": util_for(mc["prompt"], met), **met})
    return ckpts, origs


def _hl_indist(ax, labels):
    for lab in ax.get_xticklabels():
        if lab.get_text() == IN_DIST:
            lab.set_color("red"); lab.set_fontweight("bold")


def plot_vs_x(recs, origs, model, method, x_key, x_label, fixed, fname, suptitle):
    cell = [r for r in recs if r["model"] == model and r["method"] == method
            and fixed(r)]
    if not cell:
        return None
    fig, axes = plt.subplots(1, len(METRICS), figsize=(6.2 * len(METRICS), 4.4),
                             squeeze=False)
    for ci, (metric, (label, ylim)) in enumerate(METRICS.items()):
        ax = axes[0][ci]
        framings = QUANT_FRAMINGS if metric == "utility" else FRAMING_ORDER
        for fr in framings:
            pts = sorted((r[x_key], r[metric]) for r in cell
                         if r["framing"] == fr and r.get(metric) is not None)
            if pts:
                xs, ys = zip(*pts)
                ax.plot(xs, ys, marker="o", label=fr, color=FRAMING_COLOR.get(fr))
        ax.set_title(label); ax.set_xlabel(x_label); ax.set_ylabel(label)
        if ylim:
            ax.set_ylim(*ylim)
        ax.grid(True, alpha=0.3); ax.legend(fontsize=7)
    fig.suptitle(suptitle, fontsize=13)
    fig.tight_layout()
    path = os.path.join(OUT_DIR, fname)
    fig.savefig(path, dpi=130, bbox_inches="tight"); plt.close(fig)
    return path


def plot_framing_ood(recs, origs, model, method, fname, suptitle):
    cell = {r["framing"]: r for r in recs if r["model"] == model
            and r["method"] == method and r["p"] == 50 and r["epoch"] == 1.0}
    if not cell:
        return None
    fig, axes = plt.subplots(1, len(METRICS), figsize=(6.2 * len(METRICS), 4.6),
                             squeeze=False)
    xs = list(range(len(FRAMING_ORDER)))
    orig = origs.get(model, {})
    for ci, (metric, (label, ylim)) in enumerate(METRICS.items()):
        ax = axes[0][ci]
        ys = [cell[fr][metric] if fr in cell and cell[fr].get(metric) is not None
              else None for fr in FRAMING_ORDER]
        ax.plot(xs, ys, marker="o", color="#1f77b4", label="trained (p50, ep1)")
        oy = [orig[fr][metric] if fr in orig and orig[fr].get(metric) is not None
              else None for fr in FRAMING_ORDER]
        if any(v is not None for v in oy):
            ax.plot(xs, oy, marker="s", ls="--", color="black", label="original")
        ax.set_xticks(xs); ax.set_xticklabels(FRAMING_ORDER, rotation=30, ha="right")
        _hl_indist(ax, FRAMING_ORDER)
        ax.set_title(label); ax.set_ylabel(label)
        ax.set_xlabel("test framing — red = in-distribution rubric")
        if ylim:
            ax.set_ylim(*ylim)
        ax.grid(True, alpha=0.3); ax.legend(fontsize=8)
    fig.suptitle(suptitle, fontsize=13)
    fig.tight_layout()
    path = os.path.join(OUT_DIR, fname)
    fig.savefig(path, dpi=130, bbox_inches="tight"); plt.close(fig)
    return path


def write_summary(recs, origs, path):
    cols = ["Model", "Method", "Train abst %", "Epoch", "Framing", "N",
            "Correct", "Incorrect", "Abstained", "Abstention Rate",
            "Selective Acc", "Norm Utility"]
    def pct(x):
        return f"{x*100:.1f}%" if x is not None else "—"
    rows = sorted(recs, key=lambda r: (r["model"], r["method"], r["p"], r["epoch"],
                                       FRAMING_ORDER.index(r["framing"])
                                       if r["framing"] in FRAMING_ORDER else 99))
    lines = ["# HLE (Humanities/Social Science) OOD eval", "",
             "Abstention rate is exact; selective accuracy is a rule-based lower "
             "bound on exact-match items (graded with math_equal).", "",
             "| " + " | ".join(cols) + " |",
             "| " + " | ".join(["---"] * len(cols)) + " |"]
    for r in rows:
        nu = f"{r['utility']:.2f}" if r.get("utility") is not None else "—"
        lines.append("| " + " | ".join([
            MODEL_DISPLAY.get(r["model"], r["model"]),
            METHOD_DISPLAY.get(r["method"], r["method"]), f"{r['p']}%",
            f"{r['epoch']:g}", r["framing"], str(r["total"]), str(r["correct"]),
            str(r["incorrect"]), str(r["abstained"]), pct(r["abstention_rate"]),
            pct(r["selective_accuracy"]), nu]) + " |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    recs, origs = load()
    if not recs:
        print(f"[hle] no metrics found under {INPUT_DIR} — run inference/run_hle_ood.sh first.")
        return
    written = []
    pairs = sorted({(r["model"], r["method"]) for r in recs})
    for model, method in pairs:
        disp = f"{MODEL_DISPLAY.get(model, model)} {METHOD_DISPLAY.get(method, method)}"
        written.append(plot_vs_x(
            recs, origs, model, method, "epoch", "training epochs",
            lambda r: r["p"] == 50, f"HLE_{model}_{method}_vs_epoch_p50.png",
            f"{disp} — HLE (train abst 50%): metric vs epochs"))
        written.append(plot_vs_x(
            recs, origs, model, method, "p", "train-dataset abstention %",
            lambda r: r["epoch"] == 1.0, f"HLE_{model}_{method}_vs_pabst_ep1.png",
            f"{disp} — HLE (epoch 1): metric vs train abstention %"))
        written.append(plot_framing_ood(
            recs, origs, model, method, f"HLE_{model}_{method}_framing_ood.png",
            f"{disp} — HLE (train abst 50%, ep1): metric across test framings"))
    written.append(write_summary(recs, origs, os.path.join(INPUT_DIR, "hle_summary.md")))
    print(f"[hle] loaded {len(recs)} checkpoint cells, "
          f"{sum(len(v) for v in origs.values())} original cells")
    for p in written:
        if p:
            print("  wrote", p)


if __name__ == "__main__":
    main()
