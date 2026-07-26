#!/usr/bin/env python3
"""Summarize the qualitative + quantitative prompt sweep on Omni-MATH-Rule.

Replaces the hand-written `evaluation/output/qualitative_quantitative_sweep/
summary.md`, which covered only `gpt-5.4-nano` and had to be updated by hand
whenever a cell was added. This walks every graded cell in that directory and
regenerates the report, so adding the r_0 baseline (or any other rubric) is
just a matter of running the sweep and re-running this.

Per cell it reports abstention rate, selective accuracy, and Δ-accuracy against
that model's no-consequence anchor in `evaluation/output/baselines/<slug>/`
(the `standard` prompt, which carries no consequence framing at all). For
quantitative cells it also reports the score the model actually banked under
the rubric it was shown, normalized per problem.

Usage:
    python scripts/summarize_quant_qual_sweep.py
    python scripts/summarize_quant_qual_sweep.py --sweep_dir ... --out_md ...
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SWEEP_EVAL_DIR = os.path.join(REPO_ROOT, "evaluation", "output", "qualitative_quantitative_sweep")
SWEEP_RESULTS_DIR = os.path.join(REPO_ROOT, "inference", "results", "qualitative_quantitative_sweep")
BASELINE_DIR = os.path.join(REPO_ROOT, "evaluation", "output", "baselines")

# Cell names are "<model-slug>_<cell>", and model slugs themselves contain
# hyphens and dots ("gemini-3.1-flash-lite-preview"). Anchor the split on the
# cell token instead of guessing where the slug ends.
_CELL_RE = re.compile(r"^(?P<slug>.+?)_(?P<cell>QP\d+|quant_-?[\d.]+_-?[\d.]+_-?[\d.]+)$")

# Filenames in this directory encode the rubric as quant_<r_c>_<r_a>_<r_i>
# (abstain before incorrect). Note this differs from the base-model runs, which
# use _r<r_c>_<r_i>_<r_a>.
_QUANT_RE = re.compile(r"^quant_(-?[\d.]+)_(-?[\d.]+)_(-?[\d.]+)$")

# (r_c, r_a, r_i) -> the label used in the paper.
RUBRIC_LABELS: dict[tuple[float, float, float], str] = {
    (1, 0, 0): "r_0",
    (1, 0, -1): "r_1",
    (1, 0, -5): "r_5",
    (1, 0, -10): "r_10",
    (1, 0, -25): "r_25",
    (1, 0, -100): "r_100",
    (-1, 10, -10): "r_abstain",
}
RUBRIC_ORDER = ["r_0", "r_1", "r_5", "r_10", "r_25", "r_100", "r_abstain"]

QP_DESCRIPTIONS = {
    "QP1": "max-correct, no-wrong",
    "QP2": "catastrophic-consequences",
    "QP3": "career-critical",
    "QP4": "fired-if-wrong",
    "QP5": "decommissioned",
    "QP6": "professor-rubric",
    "QP7": "humanity-extinction",
}

MODEL_ORDER = [
    "claude-haiku-4-5",
    "gpt-5.4-nano",
    "gemini-3.1-flash-lite-preview",
    "deepseek-v4-pro",
    "qwen3.5-397b",
]


def parse_cell(name: str) -> dict | None:
    m = _CELL_RE.match(name)
    if not m:
        return None
    slug, cell = m.group("slug"), m.group("cell")
    q = _QUANT_RE.match(cell)
    if q:
        rubric = tuple(float(x) for x in q.groups())  # (r_c, r_a, r_i)
        label = RUBRIC_LABELS.get(rubric, "({:g},{:g},{:g})".format(*rubric))
        return {"slug": slug, "cell": cell, "kind": "quant", "rubric": rubric, "label": label}
    return {"slug": slug, "cell": cell, "kind": "qual", "rubric": None, "label": cell}


def load_baseline_acc(slug: str, baseline_dir: str) -> float | None:
    """The model's `standard`-prompt accuracy — the no-consequence anchor."""
    path = os.path.join(baseline_dir, slug, "omni-math", "math_eval_cot_metrics.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("acc")


def load_upstreams(slug: str, cell: str, results_dir: str) -> Counter:
    """Which OpenRouter upstream(s) actually served this cell, if recorded."""
    path = os.path.join(results_dir, f"{slug}_{cell}.jsonl")
    counts: Counter = Counter()
    if not os.path.exists(path):
        return counts
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                up = json.loads(line).get("upstream_provider")
                if up:
                    counts[up] += 1
    return counts


def collect(sweep_dir: str, results_dir: str, baseline_dir: str) -> list[dict]:
    rows = []
    baselines: dict[str, float | None] = {}
    for name in sorted(os.listdir(sweep_dir)):
        metrics_path = os.path.join(sweep_dir, name, "cautious_metrics.json")
        if not os.path.exists(metrics_path):
            continue
        meta = parse_cell(name)
        if meta is None:
            print(f"  (skipping unparseable cell name: {name})", file=sys.stderr)
            continue
        with open(metrics_path, "r", encoding="utf-8") as f:
            m = json.load(f)

        slug = meta["slug"]
        if slug not in baselines:
            baselines[slug] = load_baseline_acc(slug, baseline_dir)
        base_acc = baselines[slug]

        total = m["num_total"] or 1
        correct = m["num_correct"]
        incorrect = m["num_incorrect_standard"] + m["num_incorrect_mixed"]
        abstained = m["num_abstained"]
        sel_acc = m["accuracy_of_attempted"]

        # Score actually banked under the rubric the model was shown. The paper
        # reports these for the quantitative cells; they are what make "models
        # ignore the penalty" concrete (deeply negative at high |r_i|).
        score = score_per_problem = None
        if meta["kind"] == "quant":
            r_c, r_a, r_i = meta["rubric"]
            score = r_c * correct + r_a * abstained + r_i * incorrect
            score_per_problem = score / total

        rows.append({
            "slug": slug,
            "cell": meta["cell"],
            "kind": meta["kind"],
            "label": meta["label"],
            "rubric": meta["rubric"],
            "n": m["num_total"],
            "correct": correct,
            "incorrect": incorrect,
            "abstained": abstained,
            "indeterminate": m.get("num_indeterminate", 0),
            "abst_rate": 100.0 * abstained / total,
            "sel_acc": sel_acc,
            "base_acc": base_acc,
            "delta": None if base_acc is None else sel_acc - base_acc,
            "score": score,
            "score_per_problem": score_per_problem,
            "upstreams": load_upstreams(slug, meta["cell"], results_dir),
        })
    return rows


def _rubric_rank(label: str) -> int:
    return RUBRIC_ORDER.index(label) if label in RUBRIC_ORDER else len(RUBRIC_ORDER)


def _model_rank(slug: str) -> int:
    return MODEL_ORDER.index(slug) if slug in MODEL_ORDER else len(MODEL_ORDER)


def fmt(x, suffix="", nd=1):
    return "—" if x is None else f"{x:.{nd}f}{suffix}"


def fmt_signed(x, suffix=""):
    return "—" if x is None else f"{x:+.1f}{suffix}"


def write_markdown(rows: list[dict], path: str) -> None:
    out: list[str] = []
    out.append("# Qualitative + quantitative prompt sweep (Omni-MATH-Rule)")
    out.append("")
    out.append("Generated by `scripts/summarize_quant_qual_sweep.py` from "
               "`evaluation/output/qualitative_quantitative_sweep/*/cautious_metrics.json`. "
               "Do not edit by hand — re-run the script.")
    out.append("")
    out.append("Each cell was graded with `evaluation/math_eval_cautious.py`. "
               "**Abst** is `num_abstained / num_total`; **Sel acc** is "
               "`num_correct / num_attempted`; **Δ** is Sel acc minus that model's "
               "no-consequence anchor (the `standard` prompt run in "
               "`evaluation/output/baselines/<slug>/`). For quantitative cells, "
               "**Score/n** is the score the model actually banked under the rubric it "
               "was shown, per problem.")
    out.append("")
    out.append("`r_0 = (s_c, s_a, s_i) = (+1, 0, 0)` is the no-consequence quantitative "
               "baseline added for the rebuttal: abstention is offered, but a wrong "
               "answer is free. It separates *\"the model ignores how severe the penalty "
               "is\"* from *\"the model ignores whether there is a penalty at all\"* — the "
               "distinction Reviewers 27Kr and LswH both asked about. Compare each "
               "model's r_0 row against its r_1 … r_100 rows: if abstention is flat from "
               "r_0 onward, the model is not responding to the existence of a penalty, "
               "let alone its magnitude.")
    out.append("")

    slugs = sorted({r["slug"] for r in rows}, key=_model_rank)
    for slug in slugs:
        mine = [r for r in rows if r["slug"] == slug]
        base = next((r["base_acc"] for r in mine if r["base_acc"] is not None), None)
        out.append(f"## {slug}")
        out.append("")
        out.append(f"No-consequence anchor (`standard` prompt): "
                   f"**{fmt(base, '%')}** accuracy."
                   if base is not None else
                   "No-consequence anchor: **missing** — no `standard` baseline on disk, "
                   "so Δ cannot be computed.")
        out.append("")

        quant = sorted([r for r in mine if r["kind"] == "quant"],
                       key=lambda r: (_rubric_rank(r["label"]), r["label"]))
        if quant:
            out.append("### Quantitative rubrics")
            out.append("")
            out.append("| Rubric | (s_c, s_a, s_i) | n | Abst | Sel acc | Δ | Score/n | c / i / a |")
            out.append("|---|---|---:|---:|---:|---:|---:|---|")
            for r in quant:
                r_c, r_a, r_i = r["rubric"]
                out.append(
                    f"| **{r['label']}** | ({r_c:+g}, {r_a:+g}, {r_i:+g}) | {r['n']} "
                    f"| {fmt(r['abst_rate'], '%')} | {fmt(r['sel_acc'], '%')} "
                    f"| {fmt_signed(r['delta'])} | {fmt(r['score_per_problem'], '', 2)} "
                    f"| {r['correct']} / {r['incorrect']} / {r['abstained']} |"
                )
            out.append("")

        qual = sorted([r for r in mine if r["kind"] == "qual"], key=lambda r: r["label"])
        if qual:
            out.append("### Qualitative prompts")
            out.append("")
            out.append("| Prompt | | n | Abst | Sel acc | Δ | c / i / a |")
            out.append("|---|---|---:|---:|---:|---:|---|")
            for r in qual:
                desc = QP_DESCRIPTIONS.get(r["label"], "")
                out.append(
                    f"| **{r['label']}** | `{desc}` | {r['n']} "
                    f"| {fmt(r['abst_rate'], '%')} | {fmt(r['sel_acc'], '%')} "
                    f"| {fmt_signed(r['delta'])} "
                    f"| {r['correct']} / {r['incorrect']} / {r['abstained']} |"
                )
            out.append("")

        notes = [r for r in mine if len(r["upstreams"]) > 1]
        if notes:
            out.append("> **Upstream routing note.** These cells were served by more than "
                       "one OpenRouter upstream, so quantization may vary within the cell:")
            for r in sorted(notes, key=lambda r: r["label"]):
                mix = ", ".join(f"{k} ×{v}" for k, v in r["upstreams"].most_common())
                out.append(f"> - `{r['label']}`: {mix}")
            out.append("")

    out.append(_r0_section(rows))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def _r0_section(rows: list[dict]) -> str:
    """The reviewer-facing comparison: does anything change between r_0 and r_100?"""
    out = ["## r_0 vs the penalty series", ""]
    out.append("Abstention rate (%) per model as the incorrect-answer penalty grows from "
               "zero. A consequence-aware model should abstain more as the penalty rises; "
               "a model that is merely penalty-*magnitude*-insensitive would still show a "
               "step up from r_0 to r_1.")
    out.append("")
    series = [lbl for lbl in RUBRIC_ORDER if any(r["label"] == lbl for r in rows)]
    if not series:
        return ""
    out.append("| Model | " + " | ".join(series) + " |")
    out.append("|---|" + "---:|" * len(series))
    for slug in sorted({r["slug"] for r in rows}, key=_model_rank):
        cells = []
        for lbl in series:
            r = next((x for x in rows if x["slug"] == slug and x["label"] == lbl), None)
            cells.append("—" if r is None else f"{r['abst_rate']:.0f}%")
        out.append(f"| {slug} | " + " | ".join(cells) + " |")
    out.append("")
    out.append("Selective accuracy (%) over the same series:")
    out.append("")
    out.append("| Model | base | " + " | ".join(series) + " |")
    out.append("|---|---:|" + "---:|" * len(series))
    for slug in sorted({r["slug"] for r in rows}, key=_model_rank):
        mine = [r for r in rows if r["slug"] == slug]
        base = next((r["base_acc"] for r in mine if r["base_acc"] is not None), None)
        cells = []
        for lbl in series:
            r = next((x for x in mine if x["label"] == lbl), None)
            cells.append("—" if r is None else f"{r['sel_acc']:.0f}%")
        out.append(f"| {slug} | {fmt(base, '%', 0)} | " + " | ".join(cells) + " |")
    out.append("")
    return "\n".join(out)


def write_csv(rows: list[dict], path: str) -> None:
    cols = ["slug", "cell", "kind", "label", "n", "correct", "incorrect", "abstained",
            "indeterminate", "abst_rate", "sel_acc", "base_acc", "delta", "score",
            "score_per_problem", "upstreams"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda r: (_model_rank(r["slug"]),
                                             r["kind"], _rubric_rank(r["label"]), r["label"])):
            out = {k: ("" if r.get(k) is None else r.get(k)) for k in cols}
            out["upstreams"] = ";".join(f"{k}:{v}" for k, v in r["upstreams"].most_common())
            w.writerow(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sweep_dir", default=SWEEP_EVAL_DIR)
    ap.add_argument("--results_dir", default=SWEEP_RESULTS_DIR)
    ap.add_argument("--baseline_dir", default=BASELINE_DIR)
    ap.add_argument("--out_md", default=None, help="default: <sweep_dir>/summary.md")
    ap.add_argument("--out_csv", default=None, help="default: <sweep_dir>/summary.csv")
    args = ap.parse_args()

    out_md = args.out_md or os.path.join(args.sweep_dir, "summary.md")
    out_csv = args.out_csv or os.path.join(args.sweep_dir, "summary.csv")

    rows = collect(args.sweep_dir, args.results_dir, args.baseline_dir)
    if not rows:
        print(f"No graded cells found under {args.sweep_dir}", file=sys.stderr)
        return 1
    print(f"Collected {len(rows)} cells across "
          f"{len({r['slug'] for r in rows})} models")
    missing = sorted({r["slug"] for r in rows if r["base_acc"] is None})
    if missing:
        print(f"WARNING: no `standard` baseline anchor for: {', '.join(missing)} "
              f"(Δ left blank)")

    write_markdown(rows, out_md)
    write_csv(rows, out_csv)
    print(f"Wrote {out_md}")
    print(f"Wrote {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
