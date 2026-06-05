#!/usr/bin/env python3
"""Generate line-chart visualizations from the abstention-eval markdown tables
in evaluation/output/abstention_ft/.

Three views (SFT-Box and DPO always on separate subplots within a figure):
  A. train abstention 50% -> metric vs epochs (one line per framing)
  B. epoch 1             -> metric vs train-dataset abstention % (one line per framing)
  C. train abstention 50%, epoch 1 -> in-distribution (quant_m25) vs OOD framings

Metrics: abstention rate, selective accuracy, normalized utility.
"""
import glob
import math
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml

INPUT_DIR = "evaluation/output/abstention_ft"
OUT_DIR = "evaluation/output/abstention_ft/plots"
SWE_RESULTS_DIR = "swebench_pro/results"

# Exit statuses that mean "the agent never produced a usable decision" -> discarded.
SWE_ERROR_STATUSES = {
    "ContextWindowExceededError", "LimitsExceeded", "LoopDetected",
    "BadRequestError", "Timeout",
}

MODEL_DISPLAY = {"gemma4_e2b": "Gemma 4 E2B", "qwen35_9b": "Qwen3.5-9B"}
METHOD_DISPLAY = {"sft_box": "SFT-Box", "dpo": "DPO"}
METHOD_ORDER = ["sft_box", "dpo"]
FRAMING_ORDER = ["quant_m5", "quant_m25", "quant_m100", "QP1", "QP4", "QP7"]
QUANT_FRAMINGS = ["quant_m5", "quant_m25", "quant_m100"]
QUANT_PENALTY = {"quant_m5": 5, "quant_m25": 25, "quant_m100": 100}
FRAMING_COLOR = {
    "quant_m5": "#1f77b4", "quant_m25": "#d62728", "quant_m100": "#2ca02c",
    "QP1": "#9467bd", "QP4": "#ff7f0e", "QP7": "#8c564b",
}
IN_DIST = "quant_m25"  # training rubric


def to_int(v):
    return int(v) if v not in (None, "", "None") else None


def to_float(v):
    return float(v) if v not in (None, "", "None") else None


def epoch_from_slug(slug: str) -> float:
    return float(slug.rsplit("_ep", 1)[1].replace("p", "."))


def parse_md_table(path):
    with open(path, encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip()]
    if len(lines) < 3:
        return []
    header = [c.strip() for c in lines[0].strip("|").split("|")]
    out = []
    for ln in lines[2:]:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) == len(header):
            out.append(dict(zip(header, cells)))
    return out


def load_records():
    recs = []
    for path in glob.glob(os.path.join(INPUT_DIR, "*.md")):
        if os.path.basename(path).startswith("combined"):
            continue
        for r in parse_md_table(path):
            slug = r.get("variant_slug", "")
            if r.get("base_family") not in MODEL_DISPLAY or "_ep" not in slug:
                continue
            correct, incorrect = to_int(r.get("correct")), to_int(r.get("incorrect"))
            total = to_int(r.get("total")) or 100
            prompt = r.get("prompt")
            util = None
            if prompt in QUANT_PENALTY and correct is not None and incorrect is not None:
                util = (correct - QUANT_PENALTY[prompt] * incorrect) / total
            recs.append({
                "model": r.get("base_family"),
                "method": r.get("method"),
                "abst_pct": to_int(r.get("abstention_pct")),
                "epoch": epoch_from_slug(slug),
                "framing": prompt,
                "abstention_rate": to_float(r.get("abstention_rate")),
                "selective_accuracy": to_float(r.get("attempted_accuracy")),
                "utility": util,
            })
    return recs


METRICS = {
    "abstention_rate": ("Abstention rate", (0, 1)),
    "selective_accuracy": ("Selective accuracy", (0, 1)),
    "utility": ("Normalized utility", None),
}


def _highlight_indist_tick(ax):
    """Color the quant_m25 (in-distribution / trained rubric) x-tick label red."""
    for lbl in ax.get_xticklabels():
        if lbl.get_text() == IN_DIST:
            lbl.set_color("#d62728")
            lbl.set_fontweight("bold")


def plot_vs(recs, model, x_key, fixed, fname, suptitle):
    """One figure: rows = metrics, cols = methods; lines = framings; x = x_key."""
    metrics = list(METRICS)
    fig, axes = plt.subplots(len(metrics), len(METHOD_ORDER),
                             figsize=(6.2 * len(METHOD_ORDER), 4.0 * len(metrics)),
                             squeeze=False)
    for mi, metric in enumerate(metrics):
        framings = QUANT_FRAMINGS if metric == "utility" else FRAMING_ORDER
        for ci, method in enumerate(METHOD_ORDER):
            ax = axes[mi][ci]
            any_pts = False
            for fr in framings:
                pts = [(r[x_key], r[metric]) for r in recs
                       if r["model"] == model and r["method"] == method
                       and r["framing"] == fr and r[metric] is not None
                       and all(r[k] == v for k, v in fixed.items())]
                pts.sort()
                if not pts:
                    continue
                any_pts = True
                xs, ys = zip(*pts)
                ax.plot(xs, ys, marker="o", label=fr, color=FRAMING_COLOR[fr],
                        lw=2 if fr == IN_DIST else 1.4,
                        zorder=3 if fr == IN_DIST else 2)
            label, ylim = METRICS[metric]
            ax.set_title(f"{METHOD_DISPLAY[method]} — {label}")
            ax.set_xlabel("epochs" if x_key == "epoch" else "train abstention %")
            ax.set_ylabel(label)
            if ylim:
                ax.set_ylim(*ylim)
            ax.grid(True, alpha=0.3)
            if x_key == "abst_pct":
                ax.set_xticks(sorted({r["abst_pct"] for r in recs
                                      if r["model"] == model and r["abst_pct"] is not None}))
            if any_pts:
                ax.legend(fontsize=8)
    fig.suptitle(suptitle, fontsize=14, y=1.0)
    fig.tight_layout()
    path = os.path.join(OUT_DIR, fname)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_framing_ood(recs, model, fname, suptitle):
    """train abst 50%, epoch 1: metrics across framings (in-dist quant_m25 vs OOD)."""
    fig, axes = plt.subplots(1, len(METHOD_ORDER),
                             figsize=(6.5 * len(METHOD_ORDER), 4.4), squeeze=False)
    xs = list(range(len(FRAMING_ORDER)))
    for ci, method in enumerate(METHOD_ORDER):
        ax = axes[0][ci]
        sel = {r["framing"]: r for r in recs
               if r["model"] == model and r["method"] == method
               and r["abst_pct"] == 50 and r["epoch"] == 1.0}
        if not sel:
            ax.set_visible(False)
            continue
        for metric, color in [("abstention_rate", "#1f77b4"),
                              ("selective_accuracy", "#d62728")]:
            ys = [sel[fr][metric] if fr in sel and sel[fr][metric] is not None else math.nan
                  for fr in FRAMING_ORDER]
            ax.plot(xs, ys, marker="o", label=METRICS[metric][0], color=color, lw=1.8)
        idx = FRAMING_ORDER.index(IN_DIST)
        ax.axvline(idx, color="gray", ls="--", alpha=0.6)
        ax.set_title(f"{METHOD_DISPLAY[method]}")
        ax.set_xticks(xs)
        ax.set_xticklabels(FRAMING_ORDER, rotation=30, ha="right")
        _highlight_indist_tick(ax)
        ax.set_ylim(0, 1)
        ax.set_ylabel("rate / accuracy")
        ax.set_xlabel("test framing (consequence) — red = in-distribution")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, loc="lower left")
    fig.suptitle(suptitle, fontsize=14)
    fig.tight_layout()
    path = os.path.join(OUT_DIR, fname)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def _swe_framing(name: str):
    if "int5_quant1_-5_0" in name:
        return "quant_m5"
    if "int5_quant1_-25_0" in name:
        return "quant_m25"
    if "int5_quant1_-100_0" in name:
        return "quant_m100"
    for qp in ("qp1", "qp4", "qp7"):
        if f"int5_{qp}" in name:
            return qp.upper()
    return None


def load_swe_records(results_dir=SWE_RESULTS_DIR):
    """Parse Gemma SWE-bench Pro runs into the same record schema as the math
    tables. abstention_rate = #Abstained / N, selective_accuracy = #correct / N,
    where N = number of rows in eval/eval_results.json (errored runs excluded
    because they never appear in eval_results)."""
    recs = []
    for d in sorted(glob.glob(os.path.join(results_dir, "hosted_vllm_*"))):
        name = os.path.basename(d)
        yp = os.path.join(d, "exit_statuses.yaml")
        ep = os.path.join(d, "eval", "eval_results.json")
        if not (os.path.exists(yp) and os.path.exists(ep)):
            continue
        method = "sft_box" if "_sft_box_" in name else ("dpo" if "_dpo_" in name else None)
        framing = _swe_framing(name)
        m_p = re.search(r"_p(\d+)_epoch", name)
        m_e = re.search(r"epoch-([0-9p]+)_int", name)
        if not (method and framing and m_p and m_e):
            continue
        abst_pct = int(m_p.group(1))
        epoch = float(m_e.group(1).replace("p", "."))
        status = yaml.safe_load(open(yp))["instances_by_exit_status"] or {}
        import json as _json
        ev = _json.load(open(ep))
        n = len(ev)
        if n == 0:
            continue
        correct = sum(1 for v in ev.values() if v)
        incorrect = n - correct
        abstained = len(status.get("Abstained", []))
        util = None
        if framing in QUANT_PENALTY:
            util = (correct - QUANT_PENALTY[framing] * incorrect) / n
        recs.append({
            "model": "gemma4_e2b", "method": method, "abst_pct": abst_pct,
            "epoch": epoch, "framing": framing,
            "abstention_rate": abstained / n,
            "selective_accuracy": correct / n,
            "utility": util,
            "_n": n, "_correct": correct, "_incorrect": incorrect, "_abstained": abstained,
        })
    return recs


def plot_math_vs_swe(math_recs, swe_recs, model, abst_pct, epoch, fname, suptitle):
    """At a fixed (abst_pct, epoch) cell: abstention rate & selective accuracy
    across framings, comparing Math (in-domain) vs SWE-bench (OOD domain)."""
    def cell(recs, method, metric):
        sel = {r["framing"]: r[metric] for r in recs
               if r["model"] == model and r["method"] == method
               and r["abst_pct"] == abst_pct and r["epoch"] == epoch}
        return [sel.get(fr) if sel.get(fr) is not None else math.nan
                for fr in FRAMING_ORDER]

    metrics = [("abstention_rate", "Abstention rate"),
               ("selective_accuracy", "Selective accuracy")]
    fig, axes = plt.subplots(len(metrics), len(METHOD_ORDER),
                             figsize=(6.4 * len(METHOD_ORDER), 4.0 * len(metrics)),
                             squeeze=False)
    xs = list(range(len(FRAMING_ORDER)))
    idx = FRAMING_ORDER.index(IN_DIST)
    for mi, (metric, label) in enumerate(metrics):
        for ci, method in enumerate(METHOD_ORDER):
            ax = axes[mi][ci]
            ax.plot(xs, cell(math_recs, method, metric), marker="o",
                    label="Math (Omni-MATH)", color="#1f77b4", lw=2)
            ax.plot(xs, cell(swe_recs, method, metric), marker="s",
                    label="SWE-bench Pro (OOD)", color="#ff7f0e", lw=2)
            ax.axvline(idx, color="gray", ls="--", alpha=0.6)
            ax.set_title(f"{METHOD_DISPLAY[method]} — {label}")
            ax.set_xticks(xs)
            ax.set_xticklabels(FRAMING_ORDER, rotation=30, ha="right")
            _highlight_indist_tick(ax)
            ax.set_ylim(0, 1)
            ax.set_ylabel(label)
            ax.set_xlabel("test framing (consequence) — red = in-distribution")
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=8, loc="upper right")
    fig.suptitle(suptitle, fontsize=14)
    fig.tight_layout()
    path = os.path.join(OUT_DIR, fname)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def write_swe_summary(swe_recs, path):
    cols = ["Model", "Method", "Train abst %", "Epoch", "Framing", "N (eval rows)",
            "Correct", "Incorrect", "Abstained", "Abstention Rate",
            "Selective Accuracy", "Normalized Utility"]
    order = {f: i for i, f in enumerate(FRAMING_ORDER)}
    rows = sorted(swe_recs, key=lambda r: (r["method"], r["abst_pct"], r["epoch"],
                                           order.get(r["framing"], 99)))
    lines = ["# SWE-bench Pro — Gemma 4 E2B abstention eval", "",
             "Abstention rate = #Abstained / N; selective accuracy = #correct / N; "
             "N = rows in `eval/eval_results.json` (errored runs excluded). "
             "Normalized utility = `(correct − penalty×incorrect)/N` for quant framings.",
             "", "| " + " | ".join(cols) + " |",
             "| " + " | ".join(["---"] * len(cols)) + " |"]
    for r in rows:
        nu = f"{r['utility']:.2f}" if r["utility"] is not None else "—"
        lines.append("| " + " | ".join([
            MODEL_DISPLAY[r["model"]], METHOD_DISPLAY.get(r["method"], r["method"]),
            f"{r['abst_pct']}%", f"{r['epoch']:g}", r["framing"], str(r["_n"]),
            str(r["_correct"]), str(r["_incorrect"]), str(r["_abstained"]),
            f"{r['abstention_rate']*100:.1f}%", f"{r['selective_accuracy']*100:.1f}%", nu,
        ]) + " |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    recs = load_records()
    written = []

    # View A: train abstention 50% -> metrics vs epochs, per model.
    for model in MODEL_DISPLAY:
        if not any(r["model"] == model and r["abst_pct"] == 50 for r in recs):
            continue
        written.append(plot_vs(
            recs, model, x_key="epoch", fixed={"abst_pct": 50},
            fname=f"A_{model}_metrics_vs_epochs_abst50.png",
            suptitle=f"{MODEL_DISPLAY[model]} — train abstention 50%: "
                     f"metrics vs training epochs"))

    # View B: epoch 1 -> metrics vs train abstention %, per model with >1 bucket.
    for model in MODEL_DISPLAY:
        buckets = {r["abst_pct"] for r in recs
                   if r["model"] == model and r["epoch"] == 1.0 and r["abst_pct"] is not None}
        if len(buckets) < 2:
            continue
        written.append(plot_vs(
            recs, model, x_key="abst_pct", fixed={"epoch": 1.0},
            fname=f"B_{model}_metrics_vs_trainabst_ep1.png",
            suptitle=f"{MODEL_DISPLAY[model]} — epoch 1: "
                     f"metrics vs train-dataset abstention %"))

    # View C: train abstention 50%, epoch 1 -> in-distribution vs OOD framings.
    for model in MODEL_DISPLAY:
        if not any(r["model"] == model and r["abst_pct"] == 50 and r["epoch"] == 1.0
                   for r in recs):
            continue
        written.append(plot_framing_ood(
            recs, model, fname=f"C_{model}_indist_vs_ood_abst50_ep1.png",
            suptitle=f"{MODEL_DISPLAY[model]} — train abstention 50%, epoch 1: "
                     f"in-distribution (quant_m25) vs OOD consequences"))

    # View D: Math vs SWE-bench (OOD domain) at the common fully-covered cell
    # (train abstention 50%, epoch 1).
    swe_recs = load_swe_records()
    if swe_recs:
        written.append(write_swe_summary(
            swe_recs, os.path.join(INPUT_DIR, "swe_gemma_summary.md")))
        if any(r["abst_pct"] == 50 and r["epoch"] == 1.0 for r in swe_recs):
            written.append(plot_math_vs_swe(
                recs, swe_recs, model="gemma4_e2b", abst_pct=50, epoch=1.0,
                fname="D_gemma4_e2b_math_vs_swe_abst50_ep1.png",
                suptitle="Gemma 4 E2B — train abstention 50%, epoch 1: "
                         "Math vs SWE-bench Pro (out-of-distribution domain)"))

    print("wrote:")
    for p in written:
        print("  ", p)


if __name__ == "__main__":
    main()
