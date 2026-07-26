#!/usr/bin/env python3
"""Generate 4-panel scaling figures for paper_ca §Effect of Scale.

Replicates the layout of /home/paperspace/aysm/exp21c_scaling_qualitative_claude/
result_analysis/qualitative_combined.png — one 1×4 row per (family, benchmark)
showing Base Accuracy / Conditional Accuracy / Abstention Rate / Δ Accuracy
across rubrics. Story: lines are flat across scale within a family.

Outputs:
  paper_ca/figures/scaling_gemini_math.pdf
  paper_ca/figures/scaling_gemini_swe.pdf
  paper_ca/figures/scaling_qwen_math.pdf
  paper_ca/figures/scaling_qwen_swe.pdf

NEW (claude, 2026-04-30) — Arka please tweak colors/markers freely.
"""
from __future__ import annotations
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path("/home/paperspace/aysm")
OUT = Path("/home/paperspace/aysm/paper_ca/figures")
OUT.mkdir(parents=True, exist_ok=True)

CELL = json.loads((ROOT / "exp22_paper_full_rubrics/eval/cell_metrics.json").read_text())
QQ = json.loads((ROOT / "exp21_scaling/result_analysis/metrics_v6.json").read_text())
QQUAL = json.loads((ROOT / "exp21b_scaling_qualitative/result_analysis/metrics_qualitative.json").read_text())
_SF = ROOT / "qq_result" / "size_family" / "swe_size_family_metrics.json"
SF_SWE = json.loads(_SF.read_text()) if _SF.exists() else {}

QWEN_KEY = {"qwen9b": "qwen-9b", "qwen122b": "qwen-122b", "qwen397b": "qwen-397b"}
QT = {"t1": "+1_0_-1", "t5": "+1_0_-5", "t10": "+1_0_-10"}
QQL = {"qual_p1": "p1_catastrophic", "qual_p2": "p2_fired", "qual_p3": "p3_nuclear"}


def get_metric(bench, fam, rid, key):
    if bench == "swe":
        v = SF_SWE.get(f"swe__{fam}__{rid}")
        if v:
            return v.get(key)
    v = CELL.get(f"{bench}__{fam}__{rid}")
    if v:
        return v.get(key)
    if bench == "math" and fam in QWEN_KEY:
        if rid in QT:
            x = QQ.get(QWEN_KEY[fam], {}).get("thinking", {}).get(QT[rid])
            return (x or {}).get(key)
        if rid in QQL:
            x = QQUAL.get(QWEN_KEY[fam], {}).get(QQL[rid])
            return (x or {}).get(key)
    return None


def plot_family(family_key, family_label, family_models, benchmark, rubric_specs, out_path):
    """family_key: 'gemini'|'qwen'  rubric_specs: list of (rid, label) in x order."""
    fig, axes = plt.subplots(1, 4, figsize=(15, 3.7))
    panels = [
        ("base_acc_pct", "Base Accuracy (%)", (0, 100)),
        ("cond_acc_pct", "Conditional Accuracy (%)", (0, 100)),
        ("abst_rate_pct", "Abstention Rate (%)", (0, 30)),
        ("delta_acc_pp", "Δ Accuracy (pp)", None),  # autoscale
    ]
    colors = {family_models[0]: "#4F8EF7",
              family_models[1]: "#27AE60",
              family_models[2]: "#C0392B"}
    markers = {family_models[0]: "o",
               family_models[1]: "s",
               family_models[2]: "^"}

    xs = list(range(len(rubric_specs)))
    xlabels = [lab for _, lab in rubric_specs]
    rids = [rid for rid, _ in rubric_specs]

    for ax, (mk, mlabel, ylim) in zip(axes, panels):
        for fam, fam_disp in family_models.items() if isinstance(family_models, dict) else [(f, f) for f in family_models]:
            ys = [get_metric(benchmark, fam, rid, mk) for rid in rids]
            mask = [(x, y) for x, y in zip(xs, ys) if y is not None]
            if not mask:
                continue
            xx = [m[0] for m in mask]
            yy = [m[1] for m in mask]
            ax.plot(xx, yy, marker=markers[fam], linewidth=2, markersize=8,
                    color=colors[fam], label=fam_disp)
            for x_, y_ in zip(xx, yy):
                ax.annotate(f"{y_:.1f}", xy=(x_, y_), xytext=(0, 6),
                            textcoords="offset points", ha="center",
                            fontsize=8, color=colors[fam])
        ax.set_xticks(xs)
        ax.set_xticklabels(xlabels, fontsize=9)
        ax.set_ylabel(mlabel, fontsize=10)
        ax.set_title(mlabel, fontsize=11)
        ax.grid(True, alpha=0.3)
        if ylim:
            ax.set_ylim(*ylim)
        if mk == "base_acc_pct":
            ax.legend(title="Model", fontsize=8, loc="lower right")

    bench_name = "OlympiadBench (math)" if benchmark == "math" else "SWE-Bench Pro (agentic coding)"
    fig.suptitle(f"{family_label} — scaling on {bench_name}", fontsize=12, y=1.02)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_path}")


def main():
    gemini_models = {
        "gemini_lite":  "Gemini Flash-Lite",
        "gemini_flash": "Gemini Flash",
        "gemini_pro":   "Gemini Pro",
    }
    qwen_models = {
        "qwen9b":   "Qwen 9B",
        "qwen122b": "Qwen 122B",
        "qwen397b": "Qwen 397B",
    }
    math_rubrics = [
        ("t1", "t1\n(+1/-1)"), ("t5", "t5\n(+1/-5)"), ("t10", "t10\n(+1/-10)"),
        ("qual_p1", "p1\ncatastrophic"), ("qual_p2", "p2\nfired"), ("qual_p3", "p3\nnuclear"),
    ]
    swe_rubrics = [
        ("t1", "t1\n(+1/-1)"), ("t5", "t5\n(+1/-5)"), ("t10", "t10\n(+1/-10)"),
        ("qual_q1", "q1\ncatastrophic"), ("qual_q2", "q2\nfired"), ("qual_q3", "q3\nnuclear"),
    ]

    plot_family("gemini", "Gemini family", gemini_models, "math", math_rubrics,
                OUT / "scaling_gemini_math.pdf")
    plot_family("gemini", "Gemini family", gemini_models, "swe", swe_rubrics,
                OUT / "scaling_gemini_swe.pdf")
    plot_family("qwen", "Qwen family", qwen_models, "math", math_rubrics,
                OUT / "scaling_qwen_math.pdf")
    plot_family("qwen", "Qwen family", qwen_models, "swe", swe_rubrics,
                OUT / "scaling_qwen_swe.pdf")


if __name__ == "__main__":
    main()
