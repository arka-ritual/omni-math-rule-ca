#!/usr/bin/env python3
"""Summarize SWE-Bench Pro rundirs: abstention rate and selective accuracy.

Reads each rundir's `exit_statuses.yaml` (how each instance ended) and
`eval/eval_results.json` (which patches passed the official grader), and turns
them into the two metrics the paper reports.

A note on denominators
----------------------
`swebench_pro/scripts/preds_to_eval_input.py` drops instances with an empty
patch before grading (logged to `eval/skipped_empty.txt`). An abstention *is*
an empty patch, so **abstained instances never appear in eval_results.json**.
`len(eval_results)` therefore counts only instances that actually submitted
something.

`scripts/plot_abstention_summary.py:load_swe_records` computes
`abstention_rate = abstained / len(eval_results)`, i.e. abstained divided by
*attempted* rather than by total. At the low abstention rates in the paper the
two barely differ (5/95 = 5.3% vs 5/100 = 5.0%), but they diverge badly as
abstention grows, and r_abstain-style cells are exactly where abstention should
be high. This script therefore reports both:

    abst_rate        abstained / (abstained + attempted)   <- the honest one
    abst_rate_legacy abstained / attempted                 <- matches the
                                                              existing plotting
                                                              script and hence
                                                              the paper's figures

Both exclude instances that errored out (LimitsExceeded, context-window
blowups, …), which never produced a decision at all and shouldn't count either
way; they are reported separately as `errored` so a cell with a lot of them can
be spotted.

Usage:
    python scripts/swe_summarize_cells.py
    python scripts/swe_summarize_cells.py --glob 'openrouter_*_int5_quant1_0_0_*'
    python scripts/swe_summarize_cells.py --results_root swebench_pro/results
"""

from __future__ import annotations

import argparse
import collections
import csv
import fnmatch
import json
import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_ROOT = os.path.join(REPO_ROOT, "swebench_pro", "results")

# Exit statuses meaning "the agent never produced a usable decision".
# Kept in sync with scripts/plot_abstention_summary.py:SWE_ERROR_STATUSES.
ERROR_STATUSES = {
    "ContextWindowExceededError", "LimitsExceeded", "LoopDetected",
    "BadRequestError", "Timeout",
}

# Rundir names look like:
#   openrouter_openai_gpt-5.4-nano_int5_quant1_0_0_n100
#   anthropic_claude-haiku-4-5_int1_qp7_n100
#   gemini_gemini-3.1-flash-lite-preview_n100          (vanilla, no framing)
#   openrouter_openai_gpt-5.4-nano_int5_quant1_0_0      (no _n suffix: a
#                                                        breadth-first cell
#                                                        whose N grows between
#                                                        rounds, so encoding N
#                                                        in the name would
#                                                        break resume)
_CELL_RE = re.compile(
    r"^(?P<model>.+?)"
    r"(?:_int(?P<intervention>\d+))?"
    r"(?:_(?P<framing>quant-?[\d._-]+|qp\d+))?"
    r"(?:_n(?P<n>\d+)|_all)?"
    r"(?:_seed(?P<seed>\d+))?$"
)

# quant1_0_0 -> (1, 0, 0) = (r_correct, r_incorrect, r_abstain), matching
# run.sh's slug: cfg_slug="quant${RC}_${RI}_${RA}".
_QUANT_RE = re.compile(r"^quant(-?\d+)_(-?\d+)_(-?\d+)$")

RUBRIC_LABELS: dict[tuple[int, int, int], str] = {
    (1, 0, 0): "r_0",
    (1, -1, 0): "r_1",
    (1, -5, 0): "r_5",
    (1, -10, 0): "r_10",
    (1, -25, 0): "r_25",
    (1, -100, 0): "r_100",
    (-1, -10, 10): "r_abstain",
}
LABEL_ORDER = ["r_0", "r_1", "r_5", "r_10", "r_25", "r_100", "r_abstain",
               "qp1", "qp2", "qp3", "qp4", "qp5", "qp6", "qp7", "vanilla"]


def parse_rundir_name(name: str) -> dict:
    m = _CELL_RE.match(name)
    if not m:
        return {"model": name, "intervention": None, "label": "?"}
    framing = m.group("framing")
    label = "vanilla"
    if framing:
        q = _QUANT_RE.match(framing)
        if q:
            rubric = tuple(int(x) for x in q.groups())
            label = RUBRIC_LABELS.get(rubric, "({},{},{})".format(*rubric))
        else:
            label = framing
    return {
        "model": m.group("model"),
        "intervention": m.group("intervention"),
        "label": label,
        "n_requested": m.group("n"),
    }


def _statuses_from_trajectories(rundir: str) -> collections.Counter | None:
    """Cumulative exit-status counts, read from the per-instance trajectories.

    `exit_statuses.yaml` cannot be trusted on a resumed cell: mini-swe-agent's
    `RunBatchProgressManager` is constructed fresh per run with an empty
    in-memory dict and rewrites the yaml from it, so the file only ever
    describes the *most recent* run. A cell taken from N=20 to N=100 ends up
    with a yaml covering 80 instances while preds.json holds 100.

    The trajectories are one file per instance and are never rewritten across
    runs, so counting them gives the true cumulative picture.
    """
    counts: collections.Counter = collections.Counter()
    root = os.path.abspath(rundir)
    found = False
    for name in os.listdir(root):
        d = os.path.join(root, name)
        if not os.path.isdir(d) or name == "eval":
            continue
        traj = os.path.join(d, name + ".traj.json")
        if os.name == "nt":
            # Instance ids are ~135 chars and appear twice in this path, which
            # puts it past MAX_PATH; see _long_path in run_mini_on_pro.py.
            traj = "\\\\?\\" + traj
        if not os.path.exists(traj):
            continue
        try:
            with open(traj, "r", encoding="utf-8") as f:
                info = (json.load(f).get("info") or {})
        except Exception:
            continue
        status = info.get("exit_status")
        if status:
            counts[status] += 1
            found = True
    return counts if found else None


def load_cell(rundir: str) -> dict | None:
    yp = os.path.join(rundir, "exit_statuses.yaml")
    ep = os.path.join(rundir, "eval", "eval_results.json")
    if not os.path.exists(yp):
        return None

    counts = _statuses_from_trajectories(rundir)
    status_source = "trajectories"
    if counts is None:
        try:
            import yaml
        except ImportError:
            sys.exit("pyyaml is required: pip install pyyaml")
        with open(yp, "r", encoding="utf-8") as f:
            statuses = (yaml.safe_load(f) or {}).get("instances_by_exit_status") or {}
        counts = collections.Counter({k: len(v) for k, v in statuses.items()})
        status_source = "exit_statuses.yaml (last run only)"

    abstained = counts.get("Abstained", 0)
    errored = sum(v for k, v in counts.items() if k in ERROR_STATUSES)
    other = {k: v for k, v in counts.items()
             if k not in ERROR_STATUSES and k not in ("Abstained", "Submitted")}

    graded = correct = None
    if os.path.exists(ep):
        with open(ep, "r", encoding="utf-8") as f:
            ev = json.load(f)
        graded = len(ev)
        correct = sum(1 for v in ev.values() if v)

    meta = parse_rundir_name(os.path.basename(rundir))
    decided = (graded or 0) + abstained

    return {
        **meta,
        "rundir": os.path.basename(rundir),
        "abstained": abstained,
        "attempted": graded,
        "correct": correct,
        "errored": errored,
        "other_statuses": other,
        "status_source": status_source,
        "decided": decided,
        "n_instances": sum(counts.values()),
        "other_n": sum(other.values()),
        "abst_rate": (100.0 * abstained / decided) if decided else None,
        "abst_rate_legacy": (100.0 * abstained / graded) if graded else None,
        "sel_acc": (100.0 * correct / graded) if graded else None,
        "graded_missing": graded is None,
    }


def collect(results_root: str, pattern: str | None) -> list[dict]:
    rows = []
    if not os.path.isdir(results_root):
        return rows
    for name in sorted(os.listdir(results_root)):
        path = os.path.join(results_root, name)
        if not os.path.isdir(path):
            continue
        if pattern and not fnmatch.fnmatch(name, pattern):
            continue
        cell = load_cell(path)
        if cell:
            rows.append(cell)
    return rows


def _label_rank(label: str) -> int:
    return LABEL_ORDER.index(label) if label in LABEL_ORDER else len(LABEL_ORDER)


def fmt(x, suffix="%"):
    return "—" if x is None else f"{x:.1f}{suffix}"


def write_markdown(rows: list[dict], path: str) -> None:
    out = ["# SWE-Bench Pro — abstention and selective accuracy per cell", ""]
    out.append("Generated by `scripts/swe_summarize_cells.py`. Do not edit by hand.")
    out.append("")
    out.append("- **abst** = `abstained / (abstained + attempted)` — abstentions as a "
               "share of instances that reached a decision.")
    out.append("- **abst (legacy)** = `abstained / attempted`, the definition in "
               "`scripts/plot_abstention_summary.py` and hence in the paper's figures. "
               "Shown so new cells stay comparable with published ones; the two agree "
               "closely while abstention is low and diverge as it rises.")
    out.append("- **sel acc** = `correct / attempted` on the official grader.")
    out.append("- **err** = instances that never produced a decision (LimitsExceeded, "
               "LoopDetected, context-window blowups). Excluded from both rates.")
    out.append("- **other** = any remaining exit status, e.g. `RepeatedFormatError` "
               "(the model never emitted a parseable action). Also not a decision, "
               "and also excluded — surfaced here so a cell losing many instances "
               "this way is visible rather than silently shrinking the denominator.")
    out.append("- **n** = instances with a trajectory on disk. Exit statuses are counted "
               "from the per-instance trajectories, not `exit_statuses.yaml`: that file "
               "is rewritten on every run and so only describes the most recent one, "
               "which undercounts any cell that was resumed or extended.")
    out.append("")
    out.append("| Model | Int | Framing | n | abst | abst (legacy) | sel acc | "
               "abst / att / corr | err | other |")
    out.append("|---|---:|---|---:|---:|---:|---:|---|---:|---:|")
    for r in sorted(rows, key=lambda r: (r["model"], str(r["intervention"]),
                                         _label_rank(r["label"]))):
        att = "—" if r["attempted"] is None else r["attempted"]
        cor = "—" if r["correct"] is None else r["correct"]
        out.append(
            f"| `{r['model']}` | {r['intervention'] or '—'} | **{r['label']}** "
            f"| {r['n_instances']} "
            f"| {fmt(r['abst_rate'])} | {fmt(r['abst_rate_legacy'])} "
            f"| {fmt(r['sel_acc'])} | {r['abstained']} / {att} / {cor} "
            f"| {r['errored']} | {r['other_n']} |"
        )
    out.append("")

    ungraded = [r for r in rows if r["graded_missing"]]
    if ungraded:
        out.append("> **Not yet graded** (no `eval/eval_results.json`) — inference ran but "
                   "the official grader has not: "
                   + ", ".join(f"`{r['rundir']}`" for r in ungraded))
        out.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def write_csv(rows: list[dict], path: str) -> None:
    cols = ["rundir", "model", "intervention", "label", "n_instances", "abstained",
            "attempted", "correct", "errored", "other_n", "decided", "abst_rate",
            "abst_rate_legacy", "sel_acc", "status_source"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["model"], str(r["intervention"]),
                                             _label_rank(r["label"]))):
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in cols})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results_root", default=RESULTS_ROOT)
    ap.add_argument("--glob", default=None, help="only rundirs matching this pattern")
    ap.add_argument("--out_md", default=None, help="default: <results_root>/summary.md")
    ap.add_argument("--out_csv", default=None, help="default: <results_root>/summary.csv")
    args = ap.parse_args()

    rows = collect(args.results_root, args.glob)
    if not rows:
        print(f"No rundirs with exit_statuses.yaml under {args.results_root}"
              + (f" matching {args.glob!r}" if args.glob else ""), file=sys.stderr)
        return 1

    out_md = args.out_md or os.path.join(args.results_root, "summary.md")
    out_csv = args.out_csv or os.path.join(args.results_root, "summary.csv")
    write_markdown(rows, out_md)
    write_csv(rows, out_csv)
    print(f"Collected {len(rows)} cell(s)")
    print(f"Wrote {out_md}")
    print(f"Wrote {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
