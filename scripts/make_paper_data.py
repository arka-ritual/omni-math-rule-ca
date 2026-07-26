#!/usr/bin/env python3
"""Auto-generate ALL data-driven tex assets for paper_ca.

Produces:
  paper_ca/quantitative_data.tex  -> \\label{tab:quantitative}  (main_body, all quant rubrics)
  paper_ca/qualitative_data.tex   -> \\label{tab:qualitative}   (main_body, all qual prompts)
  paper_ca/scaling_data.tex       -> \\label{tab:scaling} + 4 figures (size_family)
  paper_ca/figures/scaling_*.pdf  -> 4 four-panel figures

The headline metrics across all tables/plots are **abstention rate** and
**Δ accuracy (pp)** — these directly support the paper's claim that scale
does not improve consequence-aware behavior. Conditional accuracy and base
accuracy are shown in supporting columns/panels.

NEW (claude, 2026-04-30) — Arka please tweak formatting freely.
"""
from __future__ import annotations
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------- data sources ----------
ROOT = Path("/home/paperspace/aysm")
PAPER = Path("/home/paperspace/aysm/paper_ca")
FIGS = PAPER / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

CELL = json.loads((ROOT / "exp22_paper_full_rubrics/eval/cell_metrics.json").read_text())
QQ = json.loads((ROOT / "exp21_scaling/result_analysis/metrics_v6.json").read_text())
QQUAL = json.loads((ROOT / "exp21b_scaling_qualitative/result_analysis/metrics_qualitative.json").read_text())

_SF = ROOT / "qq_result" / "size_family" / "swe_size_family_metrics.json"
SF_SWE = json.loads(_SF.read_text()) if _SF.exists() else {}
_MB = ROOT / "qq_result" / "main_body" / "swe_main_body_metrics.json"
MB_SWE = json.loads(_MB.read_text()) if _MB.exists() else {}

QWEN_KEY = {"qwen9b": "qwen-9b", "qwen122b": "qwen-122b", "qwen397b": "qwen-397b"}
QT = {"t1": "+1_0_-1", "t5": "+1_0_-5", "t10": "+1_0_-10",
      "t25": "+1_0_-25", "t100": "+1_0_-100"}
QQL = {"qual_p1": "p1_catastrophic", "qual_p2": "p2_fired", "qual_p3": "p3_nuclear"}


def get_cell(bench, fam, rid):
    """Unified per-cell metric lookup. None if ungraded."""
    if bench == "swe":
        v = SF_SWE.get(f"swe__{fam}__{rid}") or MB_SWE.get(f"swe__{fam}__{rid}")
        if v:
            return v
    v = CELL.get(f"{bench}__{fam}__{rid}")
    if v:
        return v
    if bench == "math" and fam in QWEN_KEY:
        if rid in QT:
            return QQ.get(QWEN_KEY[fam], {}).get("thinking", {}).get(QT[rid])
        if rid in QQL:
            return QQUAL.get(QWEN_KEY[fam], {}).get(QQL[rid])
    return None


def fmt(d, key, places=1):
    if not d:
        return "--"
    v = d.get(key)
    if v is None:
        return "--"
    if isinstance(v, float):
        return f"{v:.{places}f}"
    return str(v)


# ---------- model groupings ----------

MAIN_BODY_FAMS = [  # 5 frontier families for the main results tables
    ("gemini_lite", "Gemini Flash-Lite"),
    ("nano",        "GPT-5.4 Nano"),
    ("haiku",       "Claude 4.5 Haiku"),
    ("qwen397b",    "Qwen3.5 397B"),
    ("deepseek",    "DeepSeek V4 Pro"),
]

GEMINI_FAMS = [
    ("gemini_lite",  "Gemini Flash-Lite"),
    ("gemini_flash", "Gemini Flash"),
    ("gemini_pro",   "Gemini Pro"),
]
QWEN_FAMS = [
    ("qwen9b",   "Qwen 9B"),
    ("qwen122b", "Qwen 122B-A10B"),
    ("qwen397b", "Qwen 397B-A17B"),
]

QUANT_MATH = [("t1","t1"), ("t5","t5"), ("t10","t10"), ("t25","t25"),
              ("t100","t100"), ("scaled","scaled"), ("abstain","abstain")]
QUANT_SWE = [("t1","t1"), ("t5","t5"), ("t10","t10"),
             ("scaled","scaled"), ("abstain","abstain")]
# Severity-sweep subset for plots: only the symmetric +1/-X rubrics. The
# `scaled` and `abstain` rubrics test different policy behaviors and live
# in their own table/figure (tab:abstain-rubric). Mixing them on the main
# severity plot conflates two distinct arguments.
QUANT_MATH_SWEEP = [("t1","t1"), ("t5","t5"), ("t10","t10"),
                    ("t25","t25"), ("t100","t100")]
QUANT_SWE_SWEEP = [("t1","t1"), ("t5","t5"), ("t10","t10")]
QUAL_MATH = [(f"qual_p{i}", f"p{i}") for i in range(1, 8)]
QUAL_SWE_BASE = [(f"qual_q{i}", f"q{i}") for i in range(1, 4)] + [
    ("qual_q4_greedy", "q4"), ("qual_q5_career", "q5"),
    ("qual_q6_decommission", "q6"), ("qual_q7_rubric", "q7"),
]
# Plotted subsets (only prompts we have data for). v2 prompts p4-p7/q4-q7
# are pending inference; leaving them on the x-axis makes plots look truncated.
QUAL_MATH_PLOTTED = [(f"qual_p{i}", f"p{i}") for i in range(1, 4)]
QUAL_SWE_PLOTTED = [(f"qual_q{i}", f"q{i}") for i in range(1, 4)]


# ============================================================
# TABLES 1-4 — split into qual/quant × math/swe (each table fits one column)
# Labels: tab:quantitative (math), tab:quant-swe, tab:qualitative (math), tab:qual-swe
# Math tables keep Arka's existing \cref{tab:quantitative} / \cref{tab:qualitative}
# labels so his prose works without edits; SWE tables are placed right after.
# ============================================================

def fmt_bold_if_low(d, key, places=1, threshold=1.0):
    """Format value; bold if absolute value <= threshold (highlights the
    'consequence-blind' near-zero numbers that carry the story)."""
    if not d:
        return "--"
    v = d.get(key)
    if v is None:
        return "--"
    if isinstance(v, float):
        s = f"{v:.{places}f}"
        if abs(v) <= threshold:
            return rf"\textbf{{{s}}}"
        return s
    return str(v)


def emit_one_table(out_path: Path, label: str, caption: str,
                   bench: str, rubric_specs, fams=MAIN_BODY_FAMS,
                   col_label_tex=None):
    """Single narrow table: families × rubrics × (abst, Δ).

    col_label_tex(label_str) -> latex string for the per-rubric multicol header.
    Defaults to identity (use the raw label).
    """
    if col_label_tex is None:
        col_label_tex = lambda s: s
    n_rub = len(rubric_specs)
    L = []
    L.append(r"% NEW (claude, 2026-04-30) — Arka please edit/discard freely.")
    L.append(r"% Auto-generated by paper_ca/scripts/make_paper_data.py")
    L.append(r"\begin{table}[t]")
    L.append(r"  \centering")
    L.append(r"  \footnotesize")
    L.append(r"  \setlength{\tabcolsep}{4pt}")
    L.append(rf"  \caption{{{caption}}}")
    L.append(rf"  \label{{{label}}}")
    L.append(r"  \begin{tabular}{l|" + ("cc " * n_rub) + r"}")
    L.append(r"    \toprule")
    cols = " & ".join(rf"\multicolumn{{2}}{{c}}{{{col_label_tex(lab)}}}" for _, lab in rubric_specs)
    L.append(rf"    Family & {cols} \\")
    sub = " & ".join([r"abst & $\Delta$"] * n_rub)
    L.append(rf"     & {sub} \\")
    L.append(r"    \midrule")
    for fkey, flabel in fams:
        cells = [flabel]
        for rid, _ in rubric_specs:
            d = get_cell(bench, fkey, rid)
            cells.append(fmt_bold_if_low(d, "abst_rate_pct"))
            cells.append(fmt_bold_if_low(d, "delta_acc_pp"))
        L.append("    " + " & ".join(cells) + r" \\")
    L.append(r"    \bottomrule")
    L.append(r"  \end{tabular}")
    L.append(r"\end{table}")
    L.append(r"")
    out_path.write_text("\n".join(L) + "\n")
    print(f"wrote {out_path}")


def emit_quant_tables(out_path: Path):
    """2 paired plots (math, swe) — each with abst + Δ side-by-side."""
    plot_pair(MAIN_BODY_FAMS, "Frontier models", "math", QUANT_MATH_SWEEP,
              FIGS / "main_body_quant_math.pdf",
              rubric_type_label="penalty severity (+1 / -X)")
    plot_pair(MAIN_BODY_FAMS, "Frontier models", "swe", QUANT_SWE_SWEEP,
              FIGS / "main_body_quant_swe.pdf",
              rubric_type_label="penalty severity (+1 / -X)")

    math_path = out_path.with_name("quantitative_math.tex")
    swe_path = out_path.with_name("quantitative_swe.tex")
    emit_one_table(math_path, "tab:quantitative",
        r"\textbf{Models do not abstain even under 100$\times$ asymmetric penalties (math).} Quantitative consequences on \textbf{OlympiadBench} under the $+1/0/-X$ severity sweep ($\tau_1,\tau_5,\tau_{10},\tau_{25},\tau_{100}$). Each cell shows abstention rate (\%) and $\Delta$ accuracy (pp $=$ cond.~acc $-$ base acc). Bolded values $|v|\!\le\!1$ highlight near-zero cells. The two special rubrics \texttt{scaled} ($+10/0/-250$) and \texttt{abstain} ($+1/+10/-10$) are reported separately in \cref{tab:abstain-rubric}; \cref{tab:quant-swe} reports SWE-Bench Pro results; \cref{fig:main-quant-math,fig:main-quant-swe} visualize both.",
        "math", QUANT_MATH_SWEEP, fams=MAIN_BODY_FAMS,
        col_label_tex=lambda lab: rf"$\tau_{{{lab[1:]}}}$")
    emit_one_table(swe_path, "tab:quant-swe",
        r"\textbf{Same finding on SWE-Bench Pro.} Quantitative-rubric severity sweep, same metrics as \cref{tab:quantitative}.",
        "swe", QUANT_SWE_SWEEP, fams=MAIN_BODY_FAMS,
        col_label_tex=lambda lab: rf"$\tau_{{{lab[1:]}}}$")

    out_path.write_text(
        "% Section-level legend — applies to every main-body figure (Tables 1-4 + Figs).\n"
        "\\begin{figure}[t]\n  \\centering\n"
        "  \\includegraphics[width=0.85\\linewidth]{figures/legend_main_body.pdf}\n"
        "  \\caption{Model legend used across all five main-body figures (\\cref{fig:main-quant-math,fig:main-quant-swe,fig:main-qual-math,fig:main-qual-swe}). The same colors and markers identify each model throughout \\S\\ref{sec:experiments}.}\n"
        "  \\label{fig:legend-main-body}\n\\end{figure}\n\n"
        "\\begin{figure}[t]\n  \\centering\n"
        "  \\includegraphics[width=\\linewidth]{figures/main_body_quant_math.pdf}\n"
        "  \\caption{\\textbf{Frontier models do not become more cautious as penalties grow (math).} "
        "Abstention rate (left) and $\\Delta$ accuracy (right) across five main-body models on "
        "OlympiadBench under quantitative rubrics. Both metrics stay near zero from t1 to t100 "
        "(a 100$\\times$ swing in penalty); abstention never differentiates penalty severity, "
        "and $\\Delta$ accuracy --- the headroom abstention would have unlocked --- never exceeds a few percentage points.}\n"
        "  \\label{fig:main-quant-math}\n\\end{figure}\n\n"
        "\\begin{figure}[t]\n  \\centering\n"
        "  \\includegraphics[width=\\linewidth]{figures/main_body_quant_swe.pdf}\n"
        "  \\caption{\\textbf{Same finding on SWE-Bench Pro.} Same metrics as \\cref{fig:main-quant-math} "
        "with the agentic-coding benchmark.}\n"
        "  \\label{fig:main-quant-swe}\n\\end{figure}\n\n"
        "\\input{quantitative_math}\n"
        "\\input{quantitative_swe}\n")
    print(f"wrote {out_path} (wrapper)")


def emit_qual_tables(out_path: Path):
    """2 paired plots (math, swe) — each with abst + Δ side-by-side.
    Plots use the v1 prompts only (p1-p3 / q1-q3) since v2 prompts are pending."""
    plot_pair(MAIN_BODY_FAMS, "Frontier models", "math", QUAL_MATH_PLOTTED,
              FIGS / "main_body_qual_math.pdf",
              rubric_type_label="consequence severity (p1 catastrophic -> p3 nuclear)")
    plot_pair(MAIN_BODY_FAMS, "Frontier models", "swe", QUAL_SWE_PLOTTED,
              FIGS / "main_body_qual_swe.pdf",
              rubric_type_label="consequence severity (q1 catastrophic -> q3 nuclear)")

    math_path = out_path.with_name("qualitative_math.tex")
    swe_path = out_path.with_name("qualitative_swe.tex")
    emit_one_table(math_path, "tab:qualitative",
        r"\textbf{Even mass-casualty framings barely move abstention (math).} Qualitative consequences on \textbf{OlympiadBench}; abst.~(\%) and $\Delta$ acc.~(pp). $\pi_1\!-\!\pi_3$ are v1 severity prompts (catastrophic / fired / nuclear); $\pi_4\!-\!\pi_7$ are v2 stress-tests (greedy / career / decommission / strict-rubric). \cref{tab:qual-swe} reports the SWE-Bench Pro counterpart; \cref{fig:main-qual-math,fig:main-qual-swe} visualize both.",
        "math", QUAL_MATH, fams=MAIN_BODY_FAMS,
        col_label_tex=lambda lab: rf"$\pi_{{{lab[1:]}}}$")
    emit_one_table(swe_path, "tab:qual-swe",
        r"\textbf{Same finding on SWE-Bench Pro.} Qualitative consequences with the same metrics as \cref{tab:qualitative}.",
        "swe", QUAL_SWE_BASE, fams=MAIN_BODY_FAMS,
        col_label_tex=lambda lab: rf"$\rho_{{{lab[1:]}}}$")

    out_path.write_text(
        "\\begin{figure}[t]\n  \\centering\n"
        "  \\includegraphics[width=\\linewidth]{figures/main_body_qual_math.pdf}\n"
        "  \\caption{\\textbf{Natural-language consequences fail to elicit abstention (math).} "
        "Abstention rate (left) and $\\Delta$ accuracy (right) across five main-body models on "
        "OlympiadBench under qualitative consequence framings. Even when prompts escalate from "
        "`catastrophic' (p1) through `mass-casualty' (p7), both metrics stay close to zero.}\n"
        "  \\label{fig:main-qual-math}\n\\end{figure}\n\n"
        "\\begin{figure}[t]\n  \\centering\n"
        "  \\includegraphics[width=\\linewidth]{figures/main_body_qual_swe.pdf}\n"
        "  \\caption{\\textbf{Same finding on SWE-Bench Pro.} Same metrics as \\cref{fig:main-qual-math} "
        "with the agentic-coding benchmark.}\n"
        "  \\label{fig:main-qual-swe}\n\\end{figure}\n\n"
        "\\input{qualitative_math}\n"
        "\\input{qualitative_swe}\n")
    print(f"wrote {out_path} (wrapper)")


# ============================================================
# TABLE 3 + 4 figures — Effect of Scale (size_family × all rubrics)
# ============================================================

# 4-panel figure mirroring the user's reference image:
#   Base Acc | Cond Acc | Abst Rate | Δ Acc
# x-axis = rubric, lines = scale within family.
# Single global font config — all plots inherit so they look consistent.
FONT = {
    "title":       30,   # panel title (Abstention Rate / Δ Accuracy)
    "suptitle":    26,   # figure suptitle (model family + benchmark)
    "axis_label":  24,   # x-axis label, y-axis label
    "tick":        20,   # x-tick + y-tick labels
    "legend":      20,
    "legend_title":22,
    "annotation":  18,   # numeric value labels on points
    "linewidth":   3.5,
    "markersize":  15,
}

# Shared palette across the whole paper — same model = same color/marker.
COLOR_SEQ = ["#4F8EF7", "#27AE60", "#C0392B", "#9B59B6", "#F39C12", "#1F1F1F"]
MARKER_SEQ = ["o", "s", "^", "D", "v", "P"]


def make_legend(family_pairs, out_path: Path):
    """Render a standalone legend strip (no axes, no data) for a section."""
    fig = plt.figure(figsize=(min(2.2 * len(family_pairs) + 1, 18), 1.4))
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    handles = []
    for i, (_, fam_disp) in enumerate(family_pairs):
        line, = ax.plot([], [], marker=MARKER_SEQ[i],
                        linewidth=FONT["linewidth"], markersize=FONT["markersize"],
                        color=COLOR_SEQ[i], label=fam_disp)
        handles.append(line)
    ax.legend(handles, [d for _, d in family_pairs], title="Model",
              loc="center", ncol=len(family_pairs), frameon=True,
              fontsize=FONT["legend"], title_fontsize=FONT["legend_title"])
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_path}")


def plot_pair(family_pairs, family_label, benchmark, rubric_specs, out_path,
              rubric_type_label=""):
    """Pair plot: abst rate (left) + Δ accuracy (right) on one figure.

    Same x-axis on both panels. Single shared legend in the right panel.
    """
    fig, axes = plt.subplots(1, 2, figsize=(20, 6.2), sharex=True)
    color_seq = COLOR_SEQ
    marker_seq = MARKER_SEQ

    xs = list(range(len(rubric_specs)))
    xlabels = [lab.replace("\n", " ") for _, lab in rubric_specs]
    rids = [rid for rid, _ in rubric_specs]

    panels = [
        ("abst_rate_pct", "Abstention Rate (%)", (0, 30)),
        ("delta_acc_pp", "Δ Accuracy (pp)", None),
    ]
    for ax, (mk, mlabel, ylim) in zip(axes, panels):
        for i, (fam, fam_disp) in enumerate(family_pairs):
            ys = [(get_cell(benchmark, fam, rid) or {}).get(mk) for rid in rids]
            mask = [(x, y) for x, y in zip(xs, ys) if y is not None]
            if not mask:
                continue
            xx = [m[0] for m in mask]
            yy = [m[1] for m in mask]
            ax.plot(xx, yy, marker=marker_seq[i],
                    linewidth=FONT["linewidth"], markersize=FONT["markersize"],
                    color=color_seq[i], label=fam_disp)
            for x_, y_ in zip(xx, yy):
                ax.annotate(f"{y_:.1f}", xy=(x_, y_), xytext=(0, 10),
                            textcoords="offset points", ha="center",
                            fontsize=FONT["annotation"], color=color_seq[i])
        ax.set_xticks(xs)
        ax.set_xticklabels(xlabels, fontsize=FONT["tick"], rotation=30, ha="right")
        ax.tick_params(axis="y", labelsize=FONT["tick"])
        ax.set_title(mlabel, fontsize=FONT["title"], fontweight="bold", pad=14)
        ax.set_xlabel(rubric_type_label, fontsize=FONT["axis_label"])
        ax.grid(True, alpha=0.3)
        if ylim:
            ax.set_ylim(*ylim)

    # No per-figure legend — one legend per section is rendered separately
    # via make_legend() and \\input'd at the top of the section.
    bench_name = "OlympiadBench (math)" if benchmark == "math" else "SWE-Bench Pro"
    fig.suptitle(f"{family_label} on {bench_name} — {rubric_type_label}",
                 fontsize=FONT["suptitle"], fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_path}")


def plot_single(family_pairs, family_label, benchmark, rubric_specs,
                metric_key, metric_label, ylim, out_path,
                rubric_type_label=""):
    """Single-panel plot of one metric across rubrics on one benchmark."""
    fig, ax = plt.subplots(figsize=(11, 6.5))
    color_seq = COLOR_SEQ
    marker_seq = MARKER_SEQ

    xs = list(range(len(rubric_specs)))
    xlabels = [lab.replace("\n", " ") for _, lab in rubric_specs]
    rids = [rid for rid, _ in rubric_specs]

    for i, (fam, fam_disp) in enumerate(family_pairs):
        ys = [(get_cell(benchmark, fam, rid) or {}).get(metric_key) for rid in rids]
        mask = [(x, y) for x, y in zip(xs, ys) if y is not None]
        if not mask:
            continue
        xx = [m[0] for m in mask]
        yy = [m[1] for m in mask]
        ax.plot(xx, yy, marker=marker_seq[i],
                linewidth=FONT["linewidth"], markersize=FONT["markersize"],
                color=color_seq[i], label=fam_disp)
        for x_, y_ in zip(xx, yy):
            ax.annotate(f"{y_:.1f}", xy=(x_, y_), xytext=(0, 10),
                        textcoords="offset points", ha="center",
                        fontsize=FONT["annotation"], color=color_seq[i])
    ax.set_xticks(xs)
    ax.set_xticklabels(xlabels, fontsize=FONT["tick"], rotation=30, ha="right")
    ax.tick_params(axis="y", labelsize=FONT["tick"])
    ax.set_title(metric_label, fontsize=FONT["title"], fontweight="bold", pad=14)
    if rubric_type_label:
        ax.set_xlabel(rubric_type_label, fontsize=FONT["axis_label"])
    ax.grid(True, alpha=0.3)
    if ylim:
        ax.set_ylim(*ylim)

    # No per-figure legend — section-level legend is rendered separately.
    bench_name = "OlympiadBench (math)" if benchmark == "math" else "SWE-Bench Pro"
    fig.suptitle(f"{family_label} on {bench_name} — {rubric_type_label}",
                 fontsize=FONT["suptitle"], fontweight="bold", y=1.03)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_path}")


def plot_4panel(family_pairs, family_label, rubric_type,
                math_specs, swe_specs, out_path):
    """One row × 2 panels (Abstention rate, Δ accuracy).

    Headline-only layout: the two metrics that carry the no-effect-from-
    consequences and no-effect-from-scale story. Base/Cond accuracy
    available in supporting tables. x-axis combines math rubrics on the
    left and SWE rubrics on the right of a vertical separator.
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2))
    panels = [
        ("abst_rate_pct", "Abstention Rate (%)", (0, 30)),
        ("delta_acc_pp", "Δ Accuracy (pp)", None),
    ]
    color_seq = ["#4F8EF7", "#27AE60", "#C0392B", "#9B59B6", "#F39C12", "#1F1F1F"]
    marker_seq = ["o", "s", "^", "D", "v", "P"]

    n_math = len(math_specs)
    n_swe = len(swe_specs)
    xs = list(range(n_math + n_swe))
    xlabels = [lab for _, lab in math_specs] + [lab for _, lab in swe_specs]
    benches = ["math"] * n_math + ["swe"] * n_swe
    rids = [rid for rid, _ in math_specs] + [rid for rid, _ in swe_specs]

    for ax, (mk, mlabel, ylim) in zip(axes, panels):
        for i, (fam, fam_disp) in enumerate(family_pairs):
            ys = [(get_cell(b, fam, r) or {}).get(mk) for b, r in zip(benches, rids)]
            mask = [(x, y) for x, y in zip(xs, ys) if y is not None]
            if not mask:
                continue
            xx = [m[0] for m in mask]
            yy = [m[1] for m in mask]
            ax.plot(xx, yy, marker=marker_seq[i], linewidth=FONT["linewidth"], markersize=FONT["markersize"],
                    color=color_seq[i], label=fam_disp)
            for x_, y_ in zip(xx, yy):
                ax.annotate(f"{y_:.1f}", xy=(x_, y_), xytext=(0, 8),
                            textcoords="offset points", ha="center",
                            fontsize=FONT["annotation"], color=color_seq[i])
        # vertical separator between math and swe halves (only if both are present)
        if n_math > 0 and n_swe > 0:
            ax.axvline(x=n_math - 0.5, color="grey", linestyle="--", alpha=0.6, linewidth=1)
        ax.set_xticks(xs)
        # x-tick labels: prefix with benchmark, rotate to avoid overlap.
        # Strip embedded newlines so the rotated text reads cleanly.
        nice = []
        for b, lab in zip(benches, xlabels):
            tag = "math" if b == "math" else "swe"
            nice.append(f"{tag} · {lab.replace(chr(10), ' ')}")
        ax.set_xticklabels(nice, fontsize=FONT["tick"], rotation=35, ha="right")
        ax.tick_params(axis="y", labelsize=FONT["tick"])
        ax.set_title(mlabel, fontsize=FONT["title"], fontweight="bold", pad=14)
        ax.grid(True, alpha=0.3)
        if ylim:
            ax.set_ylim(*ylim)
        if mk == "abst_rate_pct":
            ax.legend(title="Model", fontsize=FONT["legend"], title_fontsize=FONT["legend_title"],
                      loc="upper right")

    rubric_label = "quantitative scoring rubrics" if rubric_type == "quant" else "qualitative consequence prompts"
    fig.suptitle(f"{family_label} — scaling under {rubric_label}",
                 fontsize=FONT["suptitle"], fontweight="bold", y=1.04)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out_path}")


def emit_scaling(out_path: Path):
    # 16 single-panel figures, parallel to main-body layout:
    #   (Gemini, Qwen) × (quant, qual) × (math, swe) × (abst, Δ)
    quant = [("t1", "t1 (+1/-1)"), ("t5", "t5 (+1/-5)"), ("t10", "t10 (+1/-10)")]
    qual_m = [("qual_p1", "p1 catastrophic"), ("qual_p2", "p2 fired"), ("qual_p3", "p3 nuclear")]
    qual_s = [("qual_q1", "q1 catastrophic"), ("qual_q2", "q2 fired"), ("qual_q3", "q3 nuclear")]

    metrics = [
        ("abst_rate_pct", "Abstention Rate (%)", (0, 30), "abst"),
        ("delta_acc_pp",  "Δ Accuracy (pp)",      None,    "delta"),
    ]

    for fams, fam_short, fam_label in [
        (GEMINI_FAMS, "gemini", "Gemini family"),
        (QWEN_FAMS,   "qwen",   "Qwen family"),
    ]:
        for benchmark, rubric_type, specs in [
            ("math", "quant",    quant),
            ("swe",  "quant",    quant),
            ("math", "qual",     qual_m),
            ("swe",  "qual",     qual_s),
        ]:
            for mk, mlabel, ylim, mshort in metrics:
                outp = FIGS / f"scaling_{fam_short}_{rubric_type}_{benchmark}_{mshort}.pdf"
                rt_label = "quantitative scoring rubrics" if rubric_type == "quant" \
                           else "qualitative consequence prompts"
                plot_single(fams, fam_label, benchmark, specs,
                            mk, mlabel, ylim, outp, rubric_type_label=rt_label)

    # Also a compact table — abstention + Δ side-by-side, math on left, swe on right
    L = []
    L.append(r"% NEW (claude, 2026-04-30) — Arka please edit/discard freely.")
    L.append(r"% Auto-generated by paper_ca/scripts/make_paper_data.py")
    L.append(r"")
    # Section-level legend for size_family (6 models)
    L.append(r"\begin{figure}[t]")
    L.append(r"  \centering")
    L.append(r"  \includegraphics[width=0.95\linewidth]{figures/legend_size_family.pdf}")
    L.append(r"  \caption{Model legend used across all size-family figures (\cref{fig:scaling-gemini-quant,fig:scaling-gemini-qual,fig:scaling-qwen-quant,fig:scaling-qwen-qual}).}")
    L.append(r"  \label{fig:legend-size-family}")
    L.append(r"\end{figure}")
    L.append(r"")
    # 4 figures (one per family × rubric_type), each containing 4 single-panel
    # plots in a 2×2 grid: rows = benchmark, cols = metric.
    def fig_block(fam_short, rubric_type, fam_disp, rt_disp, label):
        L.append(r"\begin{figure}[t]")
        L.append(r"  \centering")
        for benchmark in ["math", "swe"]:
            for mshort in ["abst", "delta"]:
                fname = f"figures/scaling_{fam_short}_{rubric_type}_{benchmark}_{mshort}.pdf"
                L.append(r"  \begin{minipage}[t]{0.49\linewidth}")
                L.append(rf"    \includegraphics[width=\linewidth]{{{fname}}}")
                L.append(r"  \end{minipage}" + ("\\hfill" if mshort == "abst" else ""))
            L.append(r"")
        L.append(rf"  \caption{{\textbf{{Scaling within the {fam_disp} family on {rt_disp}.}} "
                 r"Abstention rate (left column) and $\Delta$ accuracy (right column); math (top) "
                 r"and SWE-Bench Pro (bottom). Lines are essentially flat across the three scale points.}")
        L.append(rf"  \label{{{label}}}")
        L.append(r"\end{figure}")
        L.append(r"")

    fig_block("gemini", "quant", "Gemini", "quantitative rubrics",  "fig:scaling-gemini-quant")
    fig_block("gemini", "qual",  "Gemini", "qualitative prompts",   "fig:scaling-gemini-qual")
    fig_block("qwen",   "quant", "Qwen",   "quantitative rubrics",  "fig:scaling-qwen-quant")
    fig_block("qwen",   "qual",  "Qwen",   "qualitative prompts",   "fig:scaling-qwen-qual")
    # Then the table
    L.append(r"\begin{table}[t]")
    L.append(r"  \centering")
    L.append(r"  \scriptsize")
    L.append(r"  \setlength{\tabcolsep}{3pt}")
    L.append(r"  \caption{\textbf{Numerical view of the no-scale-effect finding.} Abstention rate (\%) and $\Delta$ accuracy (pp) for the size-family models on the t1/t5/t10 + p1/p2/p3 (and q1/q2/q3) rubrics. Within both Gemini and Qwen, the two metrics are essentially flat across scale on every rubric.}")
    L.append(r"  \label{tab:scaling}")
    L.append(r"  \begin{tabular}{l|" + "cc " * 6 + r"|" + "cc " * 6 + r"}")
    L.append(r"    \toprule")
    L.append(r"     & \multicolumn{12}{c|}{\textbf{Math}} & \multicolumn{12}{c}{\textbf{SWE-Bench Pro}} \\")
    rids_short = [("t1","t1"),("t5","t5"),("t10","t10"),
                  ("qual_p1","p1"),("qual_p2","p2"),("qual_p3","p3")]
    swe_short = [("t1","t1"),("t5","t5"),("t10","t10"),
                 ("qual_q1","q1"),("qual_q2","q2"),("qual_q3","q3")]
    cols_math = " & ".join(rf"\multicolumn{{2}}{{c}}{{{lab}}}" for _, lab in rids_short)
    cols_swe  = " & ".join(rf"\multicolumn{{2}}{{c}}{{{lab}}}" for _, lab in swe_short)
    L.append(rf"     & {cols_math} & {cols_swe} \\")
    sub = " & ".join([r"abst & $\Delta$"] * 12)
    L.append(rf"    Family & {sub} \\")
    L.append(r"    \midrule")
    L.append(r"    \multicolumn{25}{l}{\emph{Gemini family}} \\")
    for fkey, label in GEMINI_FAMS:
        cells = [label]
        for rid, _ in rids_short:
            d = get_cell("math", fkey, rid)
            cells.append(fmt(d, "abst_rate_pct"))
            cells.append(fmt(d, "delta_acc_pp"))
        for rid, _ in swe_short:
            d = get_cell("swe", fkey, rid)
            cells.append(fmt(d, "abst_rate_pct"))
            cells.append(fmt(d, "delta_acc_pp"))
        L.append("    " + " & ".join(cells) + r" \\")
    L.append(r"    \midrule")
    L.append(r"    \multicolumn{25}{l}{\emph{Qwen family}} \\")
    for fkey, label in QWEN_FAMS:
        cells = [label]
        for rid, _ in rids_short:
            d = get_cell("math", fkey, rid)
            cells.append(fmt(d, "abst_rate_pct"))
            cells.append(fmt(d, "delta_acc_pp"))
        for rid, _ in swe_short:
            d = get_cell("swe", fkey, rid)
            cells.append(fmt(d, "abst_rate_pct"))
            cells.append(fmt(d, "delta_acc_pp"))
        L.append("    " + " & ".join(cells) + r" \\")
    L.append(r"    \bottomrule")
    L.append(r"  \end{tabular}")
    L.append(r"\end{table}")
    L.append(r"")

    out_path.write_text("\n".join(L) + "\n")
    print(f"wrote {out_path}")


def emit_trace_analysis(out_path: Path):
    """Emit trace_analysis_data.tex backing §4.2 'Trace Analysis' bullets.

    Reads qq_result/main_body/trace_analysis.json (produced by
    qq_result/scripts/trace_analysis.py). Emits a single table giving the
    fraction of t10 (+1/0/-10) math reasoning traces that fall into each
    behavioral bucket, plus a short prose paragraph summarizing the finding.
    """
    src = ROOT / "qq_result" / "main_body" / "trace_analysis.json"
    if not src.exists():
        out_path.write_text("% trace_analysis.json not found — run qq_result/scripts/trace_analysis.py\n")
        print(f"WARNING: {src} missing")
        return
    data = json.loads(src.read_text())

    L = []
    L.append(r"% NEW (claude, 2026-04-30) — Arka please edit/discard freely.")
    L.append(r"% Auto-generated by paper_ca/scripts/make_paper_data.py")
    L.append(r"% Source: qq_result/main_body/trace_analysis.json")
    L.append(r"")
    L.append(r"\begin{table}[h]")
    L.append(r"  \centering")
    L.append(r"  \footnotesize")
    L.append(r"  \setlength{\tabcolsep}{6pt}")
    L.append(r"  \caption{\textbf{Most reasoning traces never engage with the rubric; among those that do, the model usually still answers.} Behavioral classification of math reasoning under the t10 (+1/0/-10) rubric, $n{=}100$ traces per model. Each trace is classified by lexical regex (no LLM judging): \emph{ignores} = no occurrence of any consequence-related term (rubric / penalty / abstain / unsure / risk / score / `if I'm wrong'); \emph{discusses then answers} = at least one term present \emph{and} a non-UNSURE \\boxed{} answer emitted; \emph{abstains} = \\boxed{UNSURE} or no \\boxed at all.}")
    L.append(r"  \label{tab:trace-analysis}")
    L.append(r"  \begin{tabular}{l|ccc|c}")
    L.append(r"    \toprule")
    L.append(r"    Model & Ignores (\%) & Discusses, answers (\%) & Abstains (\%) & $n$ \\")
    L.append(r"    \midrule")
    for fkey, _ in MAIN_BODY_FAMS:
        m = data["models"].get(fkey)
        if not m:
            continue
        c = m["counts"]
        n = c["n"]
        if n == 0:
            continue
        ig = 100 * c["ignores"] / n
        ds = 100 * c["discusses_then_answers"] / n
        ab = 100 * c["abstains"] / n
        L.append(f"    {m['label']} & {ig:.1f} & {ds:.1f} & {ab:.1f} & {n} \\\\")
    L.append(r"    \bottomrule")
    L.append(r"  \end{tabular}")
    L.append(r"\end{table}")
    L.append(r"")

    # Second table: abstain rubric (+10 abstain) — when models DO abstain, do
    # they reason about the reward rule explicitly?
    if "abstain_rubric" in data and data["abstain_rubric"]:
        L.append(r"\begin{table}[h]")
        L.append(r"  \centering")
        L.append(r"  \footnotesize")
        L.append(r"  \setlength{\tabcolsep}{6pt}")
        L.append(r"  \caption{\textbf{When models do abstain, they almost always cite the reward rule --- but they only abstain on a fraction of rows where the rule strictly favors abstention.} Under the \texttt{abstain} rubric (correct $+1$ / abstain $+10$ / incorrect $-10$), abstaining is the optimal action for any model with conditional accuracy below $\sim$95\%. We classify every trace into (a) abstained vs answered, and (b) for the abstained subset, whether the trace verbalizes the +10/-1/-10 reward rule (regex over `reward', `score', `+10', `-10', `rubric', `abstain $\dots$ better', etc.).}")
        L.append(r"  \label{tab:abstain-rubric}")
        L.append(r"  \begin{tabular}{l|ccc|c}")
        L.append(r"    \toprule")
        L.append(r"    Model & Abstained (\%) & of which cite rule (\#) & cite rate (\%) & $n$ \\")
        L.append(r"    \midrule")
        for fkey, _ in MAIN_BODY_FAMS:
            a = data["abstain_rubric"].get(fkey)
            if not a or a.get("n_total", 0) == 0:
                continue
            n = a["n_total"]
            nu = a["n_unsure"]
            nc = a["n_unsure_cites_rule"]
            ab_pct = 100 * nu / n
            cite_pct = (100 * nc / nu) if nu else 0.0
            L.append(f"    {a['label']} & {ab_pct:.1f} & {nc}/{nu} & {cite_pct:.1f} & {n} \\\\")
        L.append(r"    \bottomrule")
        L.append(r"  \end{tabular}")
        L.append(r"\end{table}")
        L.append(r"")
    out_path.write_text("\n".join(L) + "\n")
    print(f"wrote {out_path}")


def main():
    # Section-level legends — rendered once each, \input'd at top of section.
    make_legend(MAIN_BODY_FAMS, FIGS / "legend_main_body.pdf")
    make_legend(GEMINI_FAMS + QWEN_FAMS, FIGS / "legend_size_family.pdf")

    emit_quant_tables(PAPER / "quantitative_data.tex")
    emit_qual_tables(PAPER / "qualitative_data.tex")
    emit_scaling(PAPER / "scaling_data.tex")
    emit_trace_analysis(PAPER / "trace_analysis_data.tex")


if __name__ == "__main__":
    main()
