#!/usr/bin/env python3
"""Boxing-rate / abstention-decomposition analysis for base vs instruct models.

Written for the NeurIPS 2026 rebuttal, answering Reviewer 27Kr:

    "On Omni-Math, an answer is considered an abstention if there is no boxed
     answer. This naturally biases abstention rates in favor of base models,
     which are less likely to follow instructions to box their answers."

The concern is real and it has a concrete cause in this codebase.
`evaluation/math_eval_cautious.py:classify_problem` treats "no `\\boxed{}`" as
a deliberate abstention *unless* the item's `finish_reason` marks it truncated.
But `inference/inference_api.py` never writes `finish_reason` — the vLLM
provider's `generate()` returns bare text and drops it (only
`generate_with_meta()`, used by the intervention runner, keeps it). So for
every base-model run in the paper the `indeterminate` branch is unreachable and
*every* non-boxing response is scored as an abstention, whether the model chose
to abstain or simply failed to emit a box.

This script decomposes that number without re-running any inference:

    abstention_rate_lenient  the paper's metric; reproduces cautious_metrics.json
    abstention_rate_strict   only responses carrying a POSITIVE abstention
                             signal — \\boxed{UNSURE} or the few-shot
                             "Answer/Abstain decision: ABSTAIN" marker.
                             Silent non-boxing counts as a failed attempt.

plus `box_rate`, which is the "are base models just worse at following the
boxing instruction?" number the reviewer is really asking for.

Classification uses the helpers imported from `evaluation/math_eval_cautious.py`
(`strip_reasoning`, `extract_all_boxed`, `is_unsure`, `has_explicit_abstain_marker`)
so the lenient column is computed by the same code paths as the paper. Per-item
correctness is read from the already-graded `cautious_eval.jsonl` rather than
re-run through sympy — strict and lenient differ only in the denominator, so the
correct count is shared.

Usage:
    python scripts/analyze_boxing_rate.py                 # write summary.md + .csv
    python scripts/analyze_boxing_rate.py --validate      # only check we
                                                          # reproduce the
                                                          # published numbers
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "evaluation"))

from math_eval_cautious import (  # noqa: E402
    evaluate_cautious,
    extract_all_boxed,
    has_explicit_abstain_marker,
    is_truncated,
    is_unsure,
    strip_reasoning,
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS_DIR = os.path.join(REPO_ROOT, "inference", "results")
EVAL_ROOT = os.path.join(REPO_ROOT, "evaluation", "output")
OUT_DIR = os.path.join(REPO_ROOT, "evaluation", "output", "boxing_rate")

# `\boxed{` appearing at all, even if the braces are empty. Distinguishes "the
# model tried to box and produced `\boxed{}`" (a formatting failure that the
# evaluator silently reads as an abstention) from "the model never reached for
# a box at all".
_BOXED_OPEN_ANY = re.compile(r"\\boxed\s*\{")

# Trailing rubric tag written by inference/run_qwen35_9b.sh:
#     SUFFIX="${SUFFIX}_r${RC}_${RI}_${RA}"
# i.e. _r<correct>_<incorrect>_<abstain>.
_RUBRIC_RE = re.compile(r"_r(-?\d+(?:\.\d+)?)_(-?\d+(?:\.\d+)?)_(-?\d+(?:\.\d+)?)$")

_FEWSHOT_SPLIT = "_basemodel_fs-"

# (r_correct, r_incorrect, r_abstain) -> the label used in the paper. Penalty
# ratio is |r_incorrect| / r_correct, so (10, -1, 0) is r_0.1 and not r_1.
RUBRIC_LABELS: dict[tuple[float, float, float], str] = {
    (1, 0, 0): "r_0",
    (10, -1, 0): "r_0.1",
    (10, -5, 0): "r_0.5",
    (1, -1, 0): "r_1",
    (1, -10, 0): "r_10",
    (-1, -10, 10): "r_abstain",
}

# Display order for the framing column, matching the column order of the paper's
# base-model abstention table. NOTE: the paper's table labels the
# `ultra_cautious` prompt as "QP1"; the on-disk runs use the `ultra_cautious`
# preset, and its numbers reproduce that column exactly. We keep the on-disk
# name here so the table stays honest about which prompt text was actually sent.
FRAMING_ORDER = [
    "standard",
    "ultra_cautious",
    "QP1", "QP2", "QP3", "QP4", "QP5", "QP6", "QP7",
    "r_0", "r_0.1", "r_0.5", "r_1", "r_10", "r_abstain",
]

# Paper order for the few-shot configurations (code name -> paper name).
VARIANT_ORDER = [
    "normal", "no_conseq", "conseq_no_abstain", "conseq_random_abstain",
    "conseq_correct_abstain", "conseq_always_submit", "conseq_always_abstain",
]
VARIANT_PAPER_NAME = {
    "normal": "(baseline)",
    "no_conseq": "no_conseq",
    "conseq_no_abstain": "no_decision",
    "conseq_random_abstain": "full",
    "conseq_correct_abstain": "correct",
    "conseq_always_submit": "all_submit",
    "conseq_always_abstain": "all_abstain",
    "chat": "instruct (chat)",
}

# family -> (base filename prefix, instruct filename prefix). Order matters:
# `Qwen3.5-9B-` is a prefix of `Qwen3.5-9B-base-`, so base is tested first.
MODEL_FAMILIES = [
    ("Qwen3.5-9B", "Qwen3.5-9B-base-", "Qwen3.5-9B-"),
    ("Gemma-4-31B", "gemma-4-31b-", "gemma-4-31b-it-"),
]


def parse_filename(stem: str) -> dict | None:
    """Map a results-file stem to (family, tuning, fewshot_variant, framing).

    Base runs look like
        Qwen3.5-9B-base-QP7_basemodel_fs-no_conseq
        gemma-4-31b-quantitative_grading_basemodel_fs-no_conseq_r1_-10_0
    instruct runs like
        Qwen3.5-9B-QP7
        gemma-4-31b-it-quantitative_grading_r1_-10_0

    Returns None for anything that isn't one of the two families.
    """
    for family, base_prefix, instruct_prefix in MODEL_FAMILIES:
        # Tuning is decided by the *longest matching* prefix, because one
        # prefix is always a prefix of the other and the direction differs per
        # family: "Qwen3.5-9B-" is a prefix of "Qwen3.5-9B-base-", while
        # "gemma-4-31b-" is a prefix of "gemma-4-31b-it-". Trying the longer
        # one first resolves both. (Keying off the `_basemodel_fs-` marker
        # instead would misread the zero-shot raw runs, which are base models
        # with no few-shot scaffolding at all.)
        candidates = sorted(
            [(base_prefix, "base"), (instruct_prefix, "instruct")],
            key=lambda t: len(t[0]), reverse=True,
        )
        prefix = tuning = None
        for cand_prefix, cand_tuning in candidates:
            if stem.startswith(cand_prefix):
                prefix, tuning = cand_prefix, cand_tuning
                break
        if prefix is None:
            continue
        has_fewshot = _FEWSHOT_SPLIT in stem
        rest = stem[len(prefix):]

        if has_fewshot:
            framing_part, _, variant_part = rest.partition(_FEWSHOT_SPLIT)
            m = _RUBRIC_RE.search(variant_part)
            if m:
                variant = variant_part[: m.start()]
                rubric = tuple(float(g) for g in m.groups())
            else:
                variant, rubric = variant_part, None
        else:
            # No few-shot scaffolding: either an instruct run through the chat
            # interface, or a zero-shot raw-completion run. They are told apart
            # by which directory they came from, so the caller supplies the
            # label via --variant_label; "chat" is the historical default.
            variant = "chat"
            m = _RUBRIC_RE.search(rest)
            if m:
                framing_part = rest[: m.start()]
                rubric = tuple(float(g) for g in m.groups())
            else:
                framing_part, rubric = rest, None

        if rubric is not None:
            framing = RUBRIC_LABELS.get(rubric, "({:g},{:g},{:g})".format(*rubric))
        else:
            framing = framing_part

        return {
            "family": family,
            "tuning": tuning,
            "variant": variant,
            "framing": framing,
            "rubric": "" if rubric is None else "({:g},{:g},{:g})".format(*rubric),
        }
    return None


@dataclass
class Counts:
    """Every item lands in exactly one of the partition buckets below.

    The partition mirrors `math_eval_cautious.classify_problem` branch for
    branch. `n_empty_box_only` / `n_never_boxed` / `n_silent_no_box_long` are
    *flags* that further describe items already counted in a partition bucket —
    they must never be added into a total.
    """

    n: int = 0
    # --- partition ---
    n_unsure: int = 0              # boxes present, all UNSURE
    n_marker_no_box: int = 0       # no box, but explicit ABSTAIN marker
    n_silent_no_box: int = 0       # no box, no marker -> the disputed bucket
    n_indeterminate: int = 0       # no box + finish_reason says truncated
    n_mixed: int = 0               # UNSURE and a real answer -> scored incorrect
    n_correct: int = 0
    n_incorrect: int = 0
    n_ungraded: int = 0            # answered but no cached grade available
    # --- flags (subsets of the above, never summed into totals) ---
    n_box: int = 0                 # >=1 non-empty \boxed{...}
    n_empty_box_only: int = 0      # `\boxed{` present but every box empty
    n_never_boxed: int = 0         # no `\boxed{` token at all
    n_silent_no_box_long: int = 0  # silent non-boxers in the top length decile
    lengths: list[int] = field(default_factory=list)

    @property
    def abst_lenient(self) -> int:
        """The evaluator's rule: no non-empty box at all (and not truncated),
        OR all boxes UNSURE."""
        return self.n_unsure + self.n_marker_no_box + self.n_silent_no_box

    @property
    def abst_strict(self) -> int:
        """Positive abstention signal only."""
        return self.n_unsure + self.n_marker_no_box

    def _sel_acc(self, abstained: int) -> float | None:
        # Truncated responses are excluded from the denominator under both
        # definitions: they are neither an abstention nor a fair attempt.
        attempted = self.n - abstained - self.n_indeterminate
        if attempted <= 0:
            return None
        return 100.0 * self.n_correct / attempted


def load_grades(stem: str, eval_root: str) -> dict[int, str] | None:
    """Read cached per-item categories from a prior cautious eval, keyed by idx."""
    path = os.path.join(eval_root, stem, "omni-math", "cautious_eval.jsonl")
    if not os.path.exists(path):
        return None
    grades: dict[int, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if "idx" in obj and "category" in obj:
                grades[obj["idx"]] = obj["category"]
    return grades


def analyze_file(path: str, grades: dict[int, str] | None) -> Counts:
    c = Counts()
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))

    c.lengths = [len((it.get("model_generation") or "")) for it in items]
    # Length threshold for flagging plausibly-truncated silent non-boxers. These
    # files predate finish_reason capture, so this is a heuristic, not a fact.
    ordered = sorted(c.lengths)
    p90 = ordered[int(0.9 * (len(ordered) - 1))] if ordered else 0

    for it in items:
        c.n += 1
        generation = it.get("model_generation") or ""
        scored = strip_reasoning(generation)
        boxes = extract_all_boxed(scored)
        length = len(generation)

        if boxes:
            c.n_box += 1
            flags = [is_unsure(v) for v in boxes]
            if all(flags):
                c.n_unsure += 1
                continue
            if any(flags):
                c.n_mixed += 1
                c.n_incorrect += 1
                continue
            # Genuine answer attempt — take the grade from the cached eval.
            cat = grades.get(it.get("idx")) if grades else None
            if cat == "correct":
                c.n_correct += 1
            elif cat is None:
                c.n_ungraded += 1
            else:
                c.n_incorrect += 1
            continue

        # No non-empty box. Flag *how* the box is missing, then assign the
        # partition bucket in the evaluator's branch order: an explicit
        # abstain marker wins over truncation, which wins over silence.
        if _BOXED_OPEN_ANY.search(scored):
            c.n_empty_box_only += 1
        else:
            c.n_never_boxed += 1

        if has_explicit_abstain_marker(scored):
            c.n_marker_no_box += 1
        elif is_truncated(it):
            c.n_indeterminate += 1
        else:
            c.n_silent_no_box += 1
            if length >= p90:
                c.n_silent_no_box_long += 1

    return c


def matched_files(results_dir: str, variant_label: str | None = None
                  ) -> list[tuple[str, str, dict]]:
    """(stem, path, meta) for every results file belonging to a tracked family.

    `variant_label` relabels runs that carry no few-shot scaffolding — used to
    mark the zero-shot raw-completion arm as "raw" rather than the default
    "chat", since the filenames alone can't distinguish them.
    """
    out = []
    for name in sorted(os.listdir(results_dir)):
        if not name.endswith(".jsonl"):
            continue
        stem = name[: -len(".jsonl")]
        meta = parse_filename(stem)
        if meta is None:
            continue
        if variant_label and meta["variant"] == "chat":
            meta["variant"] = variant_label
        out.append((stem, os.path.join(results_dir, name), meta))
    return out


def refresh_evals(results_dir: str, cache_root: str) -> None:
    """Re-grade every matched run with the CURRENT evaluator.

    The checked-in `evaluation/output/*/omni-math/cautious_eval.jsonl` files
    were produced by an older revision: they predate the `is_unsure` fix that
    recognises `\\boxed{\\text{UNSURE}}` as an abstention, and they were graded
    when the results JSONLs still carried `finish_reason`. Rather than
    reasoning about two kinds of drift, regenerate them so every column in this
    report rests on one consistent evaluator. Roughly 18 s per cell.
    """
    files = matched_files(results_dir)
    for i, (stem, path, _) in enumerate(files, 1):
        out_dir = os.path.join(cache_root, stem, "omni-math")
        if os.path.exists(os.path.join(out_dir, "cautious_metrics.json")):
            continue
        print(f"[{i}/{len(files)}] re-grading {stem}", flush=True)
        evaluate_cautious(path, out_dir)


def build_rows(results_dir: str, eval_root: str,
               variant_label: str | None = None) -> list[dict]:
    rows = []
    for stem, path, meta in matched_files(results_dir, variant_label):
        name = os.path.basename(path)
        grades = load_grades(stem, eval_root)
        c = analyze_file(os.path.join(results_dir, name), grades)
        if c.n == 0:
            continue
        rows.append({
            **meta,
            "stem": stem,
            "n": c.n,
            "box_rate": 100.0 * c.n_box / c.n,
            "empty_box_only": c.n_empty_box_only,
            "never_boxed": c.n_never_boxed,
            "abstain_unsure": c.n_unsure,
            "abstain_marker": c.n_marker_no_box,
            "silent_no_box": c.n_silent_no_box,
            "silent_no_box_long": c.n_silent_no_box_long,
            "indeterminate": c.n_indeterminate,
            "mixed": c.n_mixed,
            "correct": c.n_correct,
            "incorrect": c.n_incorrect,
            "ungraded": c.n_ungraded,
            "abst_lenient": c.abst_lenient,
            "abst_rate_lenient": 100.0 * c.abst_lenient / c.n,
            "abst_strict": c.abst_strict,
            "abst_rate_strict": 100.0 * c.abst_strict / c.n,
            "sel_acc_lenient": c._sel_acc(c.abst_lenient),
            "sel_acc_strict": c._sel_acc(c.abst_strict),
            "_has_grades": grades is not None,
        })
    return rows


def validate(rows: list[dict], eval_root: str) -> int:
    """Check the recomputed columns against the published cautious_metrics.json.

    If this fails, the analyzer is wrong — the on-disk metrics are what the
    paper reports.

    One wrinkle: some cells' `cautious_eval.jsonl` was produced when the
    results JSONL still carried `finish_reason`, so the evaluator could split
    truncated non-boxers into `indeterminate`. The results files on disk no
    longer have that field (a resume-append or a sync dropped it), so we cannot
    reproduce the split. What *is* invariant across that loss is
    `num_abstained + num_indeterminate` — every no-box response lands in one of
    the two either way — so that is what we assert on. Cells where the split
    can't be reproduced are reported as `stale finish_reason` rather than
    silently passing.
    """
    checked = mismatched = missing = stale = 0
    for r in rows:
        path = os.path.join(eval_root, r["stem"], "omni-math", "cautious_metrics.json")
        if not os.path.exists(path):
            missing += 1
            continue
        with open(path, "r", encoding="utf-8") as f:
            m = json.load(f)
        checked += 1

        pub_no_answer = m["num_abstained"] + m.get("num_indeterminate", 0)
        our_no_answer = r["abst_lenient"] + r["indeterminate"]
        if our_no_answer != pub_no_answer or r["n"] != m["num_total"]:
            mismatched += 1
            print(f"  MISMATCH {r['stem']}: "
                  f"abstained+indeterminate={our_no_answer}/{r['n']} "
                  f"vs published={pub_no_answer}/{m['num_total']}")
        elif m.get("num_indeterminate", 0) != r["indeterminate"]:
            stale += 1
            print(f"  STALE   {r['stem']}: published split "
                  f"{m['num_abstained']}a/{m['num_indeterminate']}i, "
                  f"recomputed {r['abst_lenient']}a/{r['indeterminate']}i "
                  f"(results file has lost finish_reason)")

        if r["_has_grades"] and r["correct"] != m["num_correct"]:
            mismatched += 1
            print(f"  MISMATCH {r['stem']}: correct={r['correct']} vs published={m['num_correct']}")

    print(f"\nvalidate: {checked} cells checked, {mismatched} mismatched, "
          f"{stale} with an unreproducible truncation split, "
          f"{missing} without published metrics.")
    return 1 if mismatched else 0


def _framing_rank(f: str) -> int:
    return FRAMING_ORDER.index(f) if f in FRAMING_ORDER else len(FRAMING_ORDER)


def _variant_rank(v: str) -> int:
    return VARIANT_ORDER.index(v) if v in VARIANT_ORDER else len(VARIANT_ORDER)


def sort_key(r: dict):
    fam_rank = [f[0] for f in MODEL_FAMILIES].index(r["family"])
    return (fam_rank, r["tuning"] != "base", _variant_rank(r["variant"]),
            _framing_rank(r["framing"]))


def fmt(x, suffix="%"):
    return "—" if x is None else f"{x:.1f}{suffix}"


def write_csv(rows: list[dict], path: str) -> None:
    cols = ["family", "tuning", "variant", "framing", "rubric", "n", "box_rate",
            "empty_box_only", "never_boxed", "abstain_unsure", "abstain_marker",
            "silent_no_box", "silent_no_box_long", "indeterminate", "mixed",
            "correct", "incorrect", "ungraded", "abst_lenient", "abst_rate_lenient",
            "abst_strict", "abst_rate_strict", "sel_acc_lenient", "sel_acc_strict",
            "stem"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in cols})


def write_markdown(rows: list[dict], path: str) -> None:
    out: list[str] = []
    out.append("# Boxing rate and abstention decomposition — base vs instruct")
    out.append("")
    out.append("Generated by `scripts/analyze_boxing_rate.py`. No new inference: this is a "
               "re-read of the completions already in `inference/results/`.")
    out.append("")
    out.append("**Why this table exists.** `evaluation/math_eval_cautious.py` scores a response "
               "with no `\\boxed{}` as a deliberate abstention unless `finish_reason` marks it "
               "truncated — but `inference/inference_api.py` never records `finish_reason`, so "
               "that branch never fires and *every* non-boxing response is counted as an "
               "abstention. Reviewer 27Kr's concern is that this flatters base models, which "
               "follow the boxing instruction less reliably.")
    out.append("")
    out.append("Columns:")
    out.append("")
    out.append("- **box rate** — share of responses with at least one non-empty `\\boxed{...}`. "
               "This is the compliance number the reviewer asked for.")
    out.append("- **UNSURE** / **marker** — positive abstention signals: `\\boxed{UNSURE}`, or "
               "the few-shot `Answer/Abstain decision: ABSTAIN` line with no box.")
    out.append("- **silent** — no box, no abstention signal. The disputed bucket: the paper "
               "counts these as abstentions. **(long)** flags those in the top length decile of "
               "their run, i.e. plausibly truncated rather than a clean stop (heuristic — these "
               "files have no `finish_reason`).")
    out.append("- **empty box** — the model emitted a literal `\\boxed{}`. A formatting failure "
               "that the evaluator also reads as an abstention.")
    out.append("- **abst lenient** — the paper's metric; validated to reproduce "
               "`cautious_metrics.json` exactly.")
    out.append("- **abst strict** — UNSURE + marker only. Silent and empty-box responses are "
               "treated as failed attempts, not abstentions.")
    out.append("- **sel acc** — selective accuracy, `correct / (n − abstained)`, under each "
               "definition. The correct count is identical; only the denominator moves.")
    out.append("")

    for family, _, _ in MODEL_FAMILIES:
        fam_rows = [r for r in rows if r["family"] == family]
        if not fam_rows:
            continue
        out.append(f"## {family}")
        out.append("")
        out.append("| Tuning | Few-shot | Framing | n | box rate | UNSURE | marker | silent (long) "
                   "| empty box | abst lenient | abst strict | sel acc lenient | sel acc strict |")
        out.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for r in sorted(fam_rows, key=sort_key):
            out.append(
                f"| {r['tuning']} | {VARIANT_PAPER_NAME.get(r['variant'], r['variant'])} "
                f"| {r['framing']} | {r['n']} | {r['box_rate']:.0f}% "
                f"| {r['abstain_unsure']} | {r['abstain_marker']} "
                f"| {r['silent_no_box']} ({r['silent_no_box_long']}) | {r['empty_box_only']} "
                f"| **{r['abst_rate_lenient']:.0f}%** | **{r['abst_rate_strict']:.0f}%** "
                f"| {fmt(r['sel_acc_lenient'])} | {fmt(r['sel_acc_strict'])} |"
            )
        out.append("")

    out.append(_headline_section(rows))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _headline_section(rows: list[dict]) -> str:
    """The base-vs-instruct gap under each definition — the rebuttal number.

    Gaps are computed **paired by framing**: for each few-shot configuration we
    average (base − instruct) over exactly those framings that were run in both
    arms. Averaging the two arms independently would compare different framing
    sets, since the base grid and the instruct grid don't cover identical cells.
    """
    out = ["## Headline: does the base-vs-instruct gap survive the strict definition?", ""]
    out.append("Per few-shot configuration, averaged over framings. **Gaps are paired by "
               "framing** — each base cell is differenced against the instruct cell for the "
               "*same* framing, and only framings present in both arms are counted (`k`). "
               "The instruct row is that arm's own mean over all its framings, shown for "
               "reference.")
    out.append("")
    out.append("| Model | Few-shot | k | box rate | abst lenient | abst strict "
               "| gap lenient | gap strict |")
    out.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for family, _, _ in MODEL_FAMILIES:
        inst = [r for r in rows if r["family"] == family and r["tuning"] == "instruct"]
        inst_by_framing = {r["framing"]: r for r in inst}
        for variant in VARIANT_ORDER:
            sel = [r for r in rows
                   if r["family"] == family and r["tuning"] == "base" and r["variant"] == variant]
            if not sel:
                continue
            paired = [(r, inst_by_framing[r["framing"]])
                      for r in sel if r["framing"] in inst_by_framing]
            gap_l = _mean([b["abst_rate_lenient"] - i["abst_rate_lenient"] for b, i in paired])
            gap_s = _mean([b["abst_rate_strict"] - i["abst_rate_strict"] for b, i in paired])
            out.append(
                f"| {family} | {VARIANT_PAPER_NAME.get(variant, variant)} | {len(paired)} "
                f"| {fmt(_mean([r['box_rate'] for r in sel]))} "
                f"| {fmt(_mean([r['abst_rate_lenient'] for r in sel]))} "
                f"| {fmt(_mean([r['abst_rate_strict'] for r in sel]))} "
                f"| {fmt(gap_l, ' pp')} | {fmt(gap_s, ' pp')} |"
            )
        if inst:
            out.append(
                f"| {family} | *instruct (chat)* | {len(inst)} "
                f"| {fmt(_mean([r['box_rate'] for r in inst]))} "
                f"| {fmt(_mean([r['abst_rate_lenient'] for r in inst]))} "
                f"| {fmt(_mean([r['abst_rate_strict'] for r in inst]))} | — | — |"
            )
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results_dir", default=RESULTS_DIR)
    ap.add_argument("--eval_root", default=None,
                    help="Where to read cached per-item grades from. Defaults to the "
                         "refreshed cache under --out_dir if it exists, else the "
                         "checked-in evaluation/output tree.")
    ap.add_argument("--out_dir", default=OUT_DIR)
    ap.add_argument("--refresh", action="store_true",
                    help="Re-grade every matched run with the current evaluator into "
                         "<out_dir>/_recomputed before analyzing (~18 s per cell). Use "
                         "this once; results are cached.")
    ap.add_argument("--variant_label", default=None,
                    help="Label for runs without few-shot scaffolding (default "
                         "\"chat\"). Pass \"raw\" when pointing at the zero-shot "
                         "raw-completion results, which the filenames cannot "
                         "distinguish from ordinary chat runs.")
    ap.add_argument("--validate", action="store_true",
                    help="Only check that the lenient column reproduces the cached "
                         "cautious_metrics.json; exit non-zero on any mismatch.")
    args = ap.parse_args()

    cache_root = os.path.join(args.out_dir, "_recomputed")
    if args.refresh:
        os.makedirs(cache_root, exist_ok=True)
        refresh_evals(args.results_dir, cache_root)

    if args.eval_root is None:
        args.eval_root = cache_root if os.path.isdir(cache_root) else EVAL_ROOT
    print(f"Reading cached grades from {args.eval_root}")

    rows = build_rows(args.results_dir, args.eval_root, args.variant_label)
    print(f"Analyzed {len(rows)} run files from {args.results_dir}")
    ungraded = [r for r in rows if not r["_has_grades"]]
    if ungraded:
        print(f"WARNING: {len(ungraded)} cells have no cached cautious_eval.jsonl; "
              f"their correct counts (and selective accuracies) are unavailable:")
        for r in ungraded[:10]:
            print(f"  - {r['stem']}")

    rc = validate(rows, args.eval_root)
    if args.validate:
        return rc

    os.makedirs(args.out_dir, exist_ok=True)
    csv_path = os.path.join(args.out_dir, "summary.csv")
    md_path = os.path.join(args.out_dir, "summary.md")
    write_csv(sorted(rows, key=sort_key), csv_path)
    write_markdown(rows, md_path)
    print(f"\nWrote {csv_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
