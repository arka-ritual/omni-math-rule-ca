#!/usr/bin/env python3
"""Ablation: did finetuning improve raw math ability, or is the selective-accuracy
gain purely a consequence of abstention under CA framing?

Reads the *standard*-prompt (no CA framing) cautious-eval metrics for the
fixed-quant_m25 Gemma checkpoints and the original model, and plots, vs epoch:
  - raw accuracy        = num_correct / num_total
  - selective accuracy  = accuracy_of_attempted (correct / attempted)
  - abstention rate     = num_abstained / num_total   (spurious abstention under standard)
The original (untrained) model is drawn as a horizontal baseline on each panel.

If the checkpoints' standard-prompt accuracy ~= the original, the selective-accuracy
improvements seen under CA framing come from abstention/filtering, not better math.
"""
import glob
import json
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUTPUT_DIR = "evaluation/output/abstention_ft"
PLOTS_DIR = "evaluation/output/abstention_ft/plots"
MODEL_DISPLAY = {"gemma4_e2b": "Gemma 4 E2B", "qwen35_9b": "Qwen3.5-9B"}
SLUG_RE = re.compile(
    r"^(?P<model>gemma4_e2b|qwen35_9b)_qlora_(?P<method>\w+?)"
    r"_n500_quant_m25_k512_p(?P<p>\d+)_ep(?P<ep>[0-9p]+)$"
)
P_COLOR = {10: "#1f77b4", 25: "#ff7f0e", 50: "#2ca02c", 75: "#d62728", 90: "#9467bd"}


def read_metrics(variant):
    path = os.path.join(OUTPUT_DIR, f"{variant}__standard", "cautious_metrics.json")
    if not os.path.exists(path):
        return None
    m = json.load(open(path))
    total = m.get("num_total") or 0
    if not total:
        return None
    correct = m.get("num_correct", 0)
    attempted = m.get("num_attempted", 0)
    abstained = m.get("num_abstained", 0)
    sel = m.get("accuracy_of_attempted")
    sel = (sel / 100 if sel is not None else (correct / attempted if attempted else None))
    return {
        "raw_accuracy": correct / total,
        "selective_accuracy": sel,
        "abstention_rate": abstained / total,
        "num_total": total, "num_correct": correct,
        "num_attempted": attempted, "num_abstained": abstained,
    }


def ep_to_float(ep_tag):
    return float(ep_tag.replace("p", "."))


def load_records():
    recs = []
    for d in glob.glob(os.path.join(OUTPUT_DIR, "*_qlora_*__standard")):
        variant = os.path.basename(d).removesuffix("__standard")
        m = SLUG_RE.match(variant)
        if not m:
            continue
        met = read_metrics(variant)
        if met is None:
            continue
        recs.append({"model": m["model"], "method": m["method"], "p": int(m["p"]),
                     "epoch": ep_to_float(m["ep"]), **met})
    return recs


METRICS = [("raw_accuracy", "Raw accuracy (correct/total)"),
           ("selective_accuracy", "Selective accuracy (correct/attempted)"),
           ("abstention_rate", "Spurious abstention rate")]


def plot(recs, original, model, method, fname):
    cell = [r for r in recs if r["model"] == model and r["method"] == method]
    if not cell:
        return None
    ps = sorted({r["p"] for r in cell})
    fig, axes = plt.subplots(1, len(METRICS), figsize=(6.2 * len(METRICS), 4.4), squeeze=False)
    for ci, (metric, label) in enumerate(METRICS):
        ax = axes[0][ci]
        for p in ps:
            pts = sorted((r["epoch"], r[metric]) for r in cell
                         if r["p"] == p and r[metric] is not None)
            if pts:
                xs, ys = zip(*pts)
                ax.plot(xs, ys, marker="o", label=f"train abst {p}%", color=P_COLOR.get(p))
        if original and original.get(metric) is not None:
            ax.axhline(original[metric], color="black", ls="--", lw=1.6,
                       label="original (untrained)")
        ax.set_title(label)
        ax.set_xlabel("training epochs")
        ax.set_ylabel(label)
        if metric != "abstention_rate":
            ax.set_ylim(0, 1)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle(f"{MODEL_DISPLAY.get(model, model)} {method.upper()} — standard prompt "
                 f"(no CA framing): finetuning effect on math ability vs original", fontsize=13)
    fig.tight_layout()
    path = os.path.join(PLOTS_DIR, fname)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def pct(x):
    return f"{x*100:.1f}%" if x is not None else "—"


def write_table(recs, originals, path):
    cols = ["Model", "Method", "Train abst %", "Epoch", "N", "Correct", "Attempted",
            "Abstained", "Raw Acc", "Selective Acc", "Abstention Rate", "Δ Raw Acc vs orig"]
    rows = sorted(recs, key=lambda r: (r["model"], r["method"], r["p"], r["epoch"]))

    lines = ["# Ablation — standard-prompt (no CA framing) math ability", ""]
    for model, orig in sorted(originals.items()):
        if orig:
            lines += [f"**Original (untrained) {MODEL_DISPLAY.get(model, model)} under standard:** "
                      f"raw accuracy {pct(orig['raw_accuracy'])}, "
                      f"selective accuracy {pct(orig['selective_accuracy'])}, "
                      f"abstention {pct(orig['abstention_rate'])} (N={orig['num_total']})."]
    lines += ["", "| " + " | ".join(cols) + " |",
              "| " + " | ".join(["---"] * len(cols)) + " |"]
    for r in rows:
        orig = originals.get(r["model"])
        orig_raw = orig.get("raw_accuracy") if orig else None
        d_raw = (r["raw_accuracy"] - orig_raw) if orig_raw is not None else None
        lines.append("| " + " | ".join([
            MODEL_DISPLAY.get(r["model"], r["model"]), r["method"].upper(),
            f"{r['p']}%", f"{r['epoch']:g}", str(r["num_total"]),
            str(r["num_correct"]), str(r["num_attempted"]), str(r["num_abstained"]),
            pct(r["raw_accuracy"]), pct(r["selective_accuracy"]), pct(r["abstention_rate"]),
            (f"{d_raw*100:+.1f}pp" if d_raw is not None else "—"),
        ]) + " |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def main():
    os.makedirs(PLOTS_DIR, exist_ok=True)
    recs = load_records()
    models = sorted({r["model"] for r in recs})
    originals = {m: read_metrics(f"{m}_original") for m in models}
    written = []
    for model in models:
        for method in sorted({r["method"] for r in recs if r["model"] == model}):
            p = plot(recs, originals.get(model), model, method,
                     f"ABL_{model}_{method}_standard_no_ca.png")
            if p:
                written.append(p)
    if recs:
        written.append(write_table(recs, originals,
                                   os.path.join(OUTPUT_DIR, "ablation_standard_no_ca.md")))
    print(f"originals: { {m: (o is not None) for m, o in originals.items()} }")
    print(f"loaded {len(recs)} checkpoint records across models {models}")
    print("wrote:")
    for p in written:
        print("  ", p)


if __name__ == "__main__":
    main()
