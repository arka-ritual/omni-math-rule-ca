#!/usr/bin/env python3
"""Analyze verbal confidence, abstention, and consequence sensitivity.

This script consumes the tracked Omni-MATH intervention evaluation outputs and
produces a reproducible rebuttal-analysis package.  Intervention 1 confidence
is reparsed from its original completion; intervention 2 confidence is reparsed
from its dedicated confidence turn.  Intervention 4 decisions are never used as
outcomes because they are deterministic functions of confidence.

Run from the repository root:

    python scripts/analyze_intervention_confidence.py

The default output directory is
``evaluation/output/interventions/confidence_analysis``.
"""

from __future__ import annotations

import argparse
from concurrent.futures import TimeoutError as FutureTimeoutError
import json
import math
import os
import re
import sys
import warnings
from collections import Counter
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import expit
from patsy import build_design_matrices, dmatrix
from pebble import ProcessPool


REPO_ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = REPO_ROOT / "evaluation"
if str(EVALUATION_DIR) not in sys.path:
    sys.path.insert(0, str(EVALUATION_DIR))

from grader import math_equal  # noqa: E402
from math_eval_cautious import is_unsure  # noqa: E402
from parser import strip_string  # noqa: E402


MODELS = [
    "claude-haiku-4-5",
    "deepseek-v4-pro",
    "gemini-3.1-flash-lite-preview",
    "gpt-5.4-nano",
    "qwen3.5-397b",
]
MODEL_DISPLAY = {
    "claude-haiku-4-5": "Claude Haiku 4.5",
    "deepseek-v4-pro": "DeepSeek V4 Pro",
    "gemini-3.1-flash-lite-preview": "Gemini 3.1 Flash Lite",
    "gpt-5.4-nano": "GPT-5.4 Nano",
    "qwen3.5-397b": "Qwen3.5-397B",
}
SETTINGS = ["Quant-25", "Quant-100", "QP6", "QP7"]
SETTING_DISPLAY = {
    "Quant-25": r"$r_{25}$",
    "Quant-100": r"$r_{100}$",
    "QP6": "QP6",
    "QP7": "QP7",
}
SETTING_COLORS = {
    "Quant-25": "#1f77b4",
    "Quant-100": "#d62728",
    "QP6": "#2ca02c",
    "QP7": "#9467bd",
}
INTERVENTIONS = [1, 2]
INTERVENTION_DISPLAY = {
    1: "Single-turn, multi-step",
    2: "Multi-turn",
}
QUANT_THRESHOLDS = {
    "Quant-25": 25 / 26,
    "Quant-100": 100 / 101,
}
CONTRASTS = [
    ("Quant-25", "Quant-100", "Quant-100 − Quant-25"),
    ("QP6", "QP7", "QP7 − QP6"),
]

EXPECTED_ROWS = {1: 1997, 2: 1990}
BIN_LABELS = [f"{10*i}–{10*(i+1)}%" for i in range(10)]

_END_REASONING_RE = re.compile(r"</think\s*>|<channel\|>", re.IGNORECASE)
_NUMBER = r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))"

# Prompt-compliant lines, allowing list numbering and Markdown formatting.
_CONFIDENCE_EXPLICIT_RE = re.compile(
    rf"""
    ^[ \t]*
    (?:[-+*][ \t]+)?
    (?:\d+[ \t]*[.)][ \t]*)?
    (?:\*{{1,2}}|_{{1,2}})?
    [ \t]*confidence[ \t]*
    (?:\*{{1,2}}|_{{1,2}})?
    [ \t]*:[ \t]*
    (?:\*{{1,2}}|_{{1,2}})?
    [ \t]*(?:\\\([ \t]*)?
    {_NUMBER}[ \t]*(%)?
    """,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)

# GPT occasionally writes ``\text{CONFIDENCE: }0.98``.
_CONFIDENCE_LATEX_RE = re.compile(
    rf"""
    ^[ \t]*
    (?:[-+*][ \t]+)?
    (?:\d+[ \t]*[.)][ \t]*)?
    \\(?:text|mathrm|mathbf|mathit)\{{[ \t]*
    confidence[ \t]*(?::|=)[ \t]*\}}[ \t]*
    (?:\\\([ \t]*)?{_NUMBER}[ \t]*(%)?
    """,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)

# Used only if no explicit line exists and all matches resolve to one value.
_CONFIDENCE_PROSE_RE = re.compile(
    rf"""
    \bconfidence\b[ \t]*
    (?:\*{{1,2}}|_{{1,2}})?[ \t]*
    (?::|=|\bis\b|\bof\b|\bat\b)[ \t]*
    (?:\*{{1,2}}|_{{1,2}})?[ \t]*
    (?:\\\([ \t]*)?{_NUMBER}[ \t]*(%)?
    """,
    re.IGNORECASE | re.VERBOSE,
)

_ANSWER_LINE_RE = re.compile(
    r"""
    ^[ \t]*
    (?:[-+*][ \t]+)?
    (?:1[ \t]*[.)][ \t]*)?
    (?:\*{1,2}|_{1,2})?
    [ \t]*answer[ \t]*
    (?:\*{1,2}|_{1,2})?
    [ \t]*:[ \t]*
    (?:\*{1,2}|_{1,2})?
    [ \t]*(.+?)[ \t]*$
    """,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)

_OUTER_BOX_RE = re.compile(r"^\\boxed\{(.*)\}$", re.DOTALL)


def strip_committed_text(text: str | None) -> str:
    """Discard model scratch text through the final reasoning delimiter."""
    text = text or ""
    matches = list(_END_REASONING_RE.finditer(text))
    return text[matches[-1].end() :] if matches else text


def normalize_confidence(raw: str, explicit_percent: bool) -> dict:
    """Normalize a reported confidence to [0, 1] while preserving scale flags."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return {
            "value": math.nan,
            "normalization": "invalid_numeric",
            "valid": False,
        }
    if not math.isfinite(value) or value < 0:
        return {
            "value": math.nan,
            "normalization": "out_of_range",
            "valid": False,
        }
    if explicit_percent:
        value /= 100
        normalization = "explicit_percent"
    elif value <= 1:
        normalization = "unit_interval"
    elif value <= 100:
        value /= 100
        normalization = "implicit_percent"
    else:
        return {
            "value": math.nan,
            "normalization": "out_of_range",
            "valid": False,
        }
    return {
        "value": value,
        "normalization": normalization,
        "valid": 0 <= value <= 1,
    }


def _confidence_matches(pattern: re.Pattern, text: str, route: str) -> list[dict]:
    out = []
    for match in pattern.finditer(text):
        normalized = normalize_confidence(match.group(1), bool(match.group(2)))
        out.append(
            {
                "raw": match.group(1),
                "line": match.group(0).strip(),
                "position": match.start(),
                "route": route,
                **normalized,
            }
        )
    return out


def parse_confidence(text: str | None) -> dict:
    """Parse confidence from the committed completion with an audit trail."""
    committed = strip_committed_text(text)
    matches = _confidence_matches(
        _CONFIDENCE_EXPLICIT_RE, committed, "explicit_line"
    )
    matches.extend(
        _confidence_matches(_CONFIDENCE_LATEX_RE, committed, "latex_line")
    )
    matches.sort(key=lambda item: item["position"])

    if matches:
        valid = [m for m in matches if m["valid"]]
        # The intervention contract assigns confidence in step 2, before
        # consequence-aware decision reasoning in step 3. Later occurrences
        # can be threshold algebra or a repeated value, so use the first
        # prompt-compliant declaration (matching parse_confidence_line).
        chosen = valid[0] if valid else matches[0]
        distinct = sorted(
            {round(m["value"], 12) for m in valid if math.isfinite(m["value"])}
        )
        return {
            "confidence_raw": chosen["raw"],
            "confidence_line": chosen["line"],
            "confidence": chosen["value"],
            "confidence_parse_status": (
                "parsed_conflicting" if len(distinct) > 1 else "parsed"
            )
            if chosen["valid"]
            else "invalid",
            "confidence_parse_route": chosen["route"],
            "confidence_normalization": chosen["normalization"],
            "confidence_match_count": len(matches),
            "confidence_conflict": len(distinct) > 1,
        }

    prose = _confidence_matches(_CONFIDENCE_PROSE_RE, committed, "prose_fallback")
    valid_prose = [m for m in prose if m["valid"]]
    distinct = sorted(
        {round(m["value"], 12) for m in valid_prose if math.isfinite(m["value"])}
    )
    if len(distinct) == 1:
        chosen = valid_prose[0]
        return {
            "confidence_raw": chosen["raw"],
            "confidence_line": chosen["line"],
            "confidence": chosen["value"],
            "confidence_parse_status": "parsed_prose",
            "confidence_parse_route": chosen["route"],
            "confidence_normalization": chosen["normalization"],
            "confidence_match_count": len(prose),
            "confidence_conflict": False,
        }
    return {
        "confidence_raw": "",
        "confidence_line": "",
        "confidence": math.nan,
        "confidence_parse_status": "ambiguous" if len(distinct) > 1 else "missing",
        "confidence_parse_route": "prose_fallback" if prose else "none",
        "confidence_normalization": "none",
        "confidence_match_count": len(prose),
        "confidence_conflict": len(distinct) > 1,
    }


def _strip_answer_wrappers(value: str) -> str:
    value = value.strip()
    value = re.sub(r"(?:\*{1,2}|_{1,2})\s*$", "", value).strip()
    for left, right in (("$", "$"), (r"\(", r"\)"), (r"\[", r"\]")):
        if value.startswith(left) and value.endswith(right):
            value = value[len(left) : -len(right)].strip()
    match = _OUTER_BOX_RE.match(value)
    if match:
        value = match.group(1).strip()
    return value


def parse_intervention1_answer(text: str | None) -> dict:
    """Extract the candidate answer that intervention 1 assigned confidence to."""
    committed = strip_committed_text(text)
    matches = list(_ANSWER_LINE_RE.finditer(committed))
    if not matches:
        return {
            "candidate_answer_raw": "",
            "candidate_answer": "",
            "candidate_parse_status": "missing",
            "candidate_match_count": 0,
        }
    # Step 1's first formal ANSWER line is the candidate that receives the
    # step-2 confidence. Later answer mentions belong to decision reasoning.
    raw = matches[0].group(1).strip()
    answer = _strip_answer_wrappers(raw)
    if not answer or is_unsure(answer):
        return {
            "candidate_answer_raw": raw,
            "candidate_answer": "",
            "candidate_parse_status": "abstain_or_empty",
            "candidate_match_count": len(matches),
        }
    return {
        "candidate_answer_raw": raw,
        "candidate_answer": answer,
        "candidate_parse_status": (
            "parsed_multiple" if len({m.group(1).strip() for m in matches}) > 1
            else "parsed"
        ),
        "candidate_match_count": len(matches),
    }


def parse_intervention2_answer(value: object) -> dict:
    raw = "" if value is None else str(value).strip()
    answer = _strip_answer_wrappers(raw)
    if (
        not answer
        or answer.lower() in {"[unparsed]", "[no answer parsed]"}
        or is_unsure(answer)
    ):
        return {
            "candidate_answer_raw": raw,
            "candidate_answer": "",
            "candidate_parse_status": "missing",
            "candidate_match_count": 0,
        }
    return {
        "candidate_answer_raw": raw,
        "candidate_answer": answer,
        "candidate_parse_status": "stored_turn1",
        "candidate_match_count": 1,
    }


def normalize_stored_confidence(value: object) -> float:
    if value in (None, "", "[unparsed]"):
        return math.nan
    normalized = normalize_confidence(str(value), explicit_percent=False)
    return normalized["value"] if normalized["valid"] else math.nan


def _grade_candidate_worker(key: tuple[str, str]) -> tuple[tuple[str, str], bool]:
    """Worker entrypoint using the repository evaluator's equivalence rules."""
    candidate, ground_truth = key
    prediction = strip_string(candidate)
    return key, bool(math_equal(prediction, ground_truth, timeout=False))


def grade_candidates(
    frame: pd.DataFrame, workers: int | None = None, timeout: float = 10.0
) -> pd.Series:
    """Grade unique pairs with repository rules and a stable hard timeout.

    The evaluator's one-second nested symbolic timeout is sensitive to machine
    load near the boundary. We instead put the same math_equal computation in a
    disposable worker with a more generous per-pair limit. As in the evaluator,
    a timeout is an ordinary non-match rather than missing data.
    """
    workers = workers or min(16, os.cpu_count() or 1)
    keys = sorted(
        {
            (str(candidate), str(ground_truth))
            for candidate, ground_truth in zip(
                frame["candidate_answer"], frame["ground_truth"]
            )
            if str(candidate)
        }
    )
    results: dict[tuple[str, str], float] = {}
    with ProcessPool(max_workers=workers) as pool:
        futures = {
            key: pool.schedule(
                _grade_candidate_worker, args=(key,), timeout=timeout
            )
            for key in keys
        }
        for key, future in futures.items():
            try:
                _, correct = future.result()
                results[key] = float(correct)
            except FutureTimeoutError:
                results[key] = 0.0
            except Exception as exc:
                warnings.warn(
                    f"candidate grading failed for {key!r}: "
                    f"{type(exc).__name__}: {exc}"
                )
                results[key] = math.nan
    return pd.Series(
        [
            results.get((str(candidate), str(ground_truth)), math.nan)
            if str(candidate)
            else math.nan
            for candidate, ground_truth in zip(
                frame["candidate_answer"], frame["ground_truth"]
            )
        ],
        index=frame.index,
        dtype=float,
    )


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def extract_records(input_dir: Path, grade_workers: int | None = None) -> pd.DataFrame:
    records: list[dict] = []

    for model in MODELS:
        for intervention in INTERVENTIONS:
            for setting in SETTINGS:
                path = input_dir / f"{model}_int{intervention}_{setting}" / "cautious_eval.jsonl"
                if not path.exists():
                    raise FileNotFoundError(path)
                rows = load_jsonl(path)

                stored_int4: dict[int, object] = {}
                if intervention == 1:
                    int4_path = (
                        input_dir / f"{model}_int4_{setting}" / "cautious_eval.jsonl"
                    )
                    if int4_path.exists():
                        stored_int4 = {
                            int(row["idx"]): row.get("int4_confidence")
                            for row in load_jsonl(int4_path)
                        }

                for row in rows:
                    if intervention == 1:
                        confidence_source = row.get("model_generation", "")
                        candidate = parse_intervention1_answer(confidence_source)
                        stored_raw = stored_int4.get(int(row["idx"]))
                    else:
                        turns = row.get("turns") or []
                        confidence_source = (
                            turns[1].get("text", "") if len(turns) > 1 else ""
                        )
                        candidate = parse_intervention2_answer(
                            row.get("predicted_answer_turn1")
                        )
                        stored_raw = row.get("stated_confidence")

                    confidence = parse_confidence(confidence_source)
                    ground_truth = str(row.get("gt", ""))
                    stored_normalized = normalize_stored_confidence(stored_raw)
                    parsed_value = confidence["confidence"]
                    if math.isfinite(parsed_value) and math.isfinite(stored_normalized):
                        stored_match: bool | float = bool(
                            math.isclose(parsed_value, stored_normalized, abs_tol=1e-12)
                        )
                    else:
                        stored_match = math.nan

                    category = row.get("category", "")
                    records.append(
                        {
                            "model": model,
                            "model_display": MODEL_DISPLAY[model],
                            "intervention": intervention,
                            "intervention_display": INTERVENTION_DISPLAY[intervention],
                            "setting": setting,
                            "setting_display": SETTING_DISPLAY[setting],
                            "consequence_type": (
                                "quantitative" if setting.startswith("Quant") else "qualitative"
                            ),
                            "penalty": (
                                25 if setting == "Quant-25"
                                else 100 if setting == "Quant-100"
                                else math.nan
                            ),
                            "decision_threshold": QUANT_THRESHOLDS.get(setting, math.nan),
                            "idx": int(row["idx"]),
                            "difficulty": row.get("difficulty"),
                            "domain": json.dumps(row.get("domain", []), ensure_ascii=False),
                            "source": row.get("source", ""),
                            "category": category,
                            "abstained": int(category == "abstained"),
                            "outcome_valid": category != "indeterminate",
                            "final_score": bool(row.get("score", False)),
                            "ground_truth": ground_truth,
                            **candidate,
                            **confidence,
                            "stored_confidence_raw": (
                                "" if stored_raw is None else str(stored_raw)
                            ),
                            "stored_confidence_normalized": stored_normalized,
                            "stored_confidence_match": stored_match,
                            "source_path": str(path.relative_to(REPO_ROOT)),
                        }
                    )

    frame = pd.DataFrame.from_records(records)
    frame["candidate_correct"] = grade_candidates(frame, workers=grade_workers)
    for intervention, expected in EXPECTED_ROWS.items():
        actual = int((frame["intervention"] == intervention).sum())
        if actual != expected:
            raise AssertionError(
                f"intervention {intervention}: expected {expected} rows, found {actual}"
            )
    expected_cells = {
        (model, intervention, setting)
        for model in MODELS
        for intervention in INTERVENTIONS
        for setting in SETTINGS
    }
    actual_cells = set(
        frame[["model", "intervention", "setting"]]
        .itertuples(index=False, name=None)
    )
    if actual_cells != expected_cells:
        raise AssertionError(
            f"cell mismatch: missing={expected_cells - actual_cells}, "
            f"unexpected={actual_cells - expected_cells}"
        )
    return frame


def analytic_rows(frame: pd.DataFrame, exclude_mixed: bool = False) -> pd.DataFrame:
    keep = frame["outcome_valid"] & frame["confidence"].notna()
    if exclude_mixed:
        keep &= frame["category"] != "incorrect_mixed"
    return frame.loc[keep].copy()


def raw_bin_index(values: pd.Series) -> pd.Series:
    arr = np.floor(values.astype(float).to_numpy() * 10).astype(int)
    return pd.Series(np.clip(arr, 0, 9), index=values.index)


def add_confidence_bins(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["raw_bin"] = raw_bin_index(out["confidence"])
    ranks = out.groupby(["model", "intervention"], sort=False)["confidence"].rank(
        method="average"
    )
    sizes = out.groupby(["model", "intervention"], sort=False)["confidence"].transform(
        "size"
    )
    out["confidence_percentile"] = 100 * (ranks - 0.5) / sizes
    out["percentile_bin"] = np.clip(
        np.floor(out["confidence_percentile"] / 10).astype(int), 0, 9
    )
    return out


def wilson_interval(successes: int, total: int, alpha: float = 0.05) -> tuple[float, float]:
    if total <= 0:
        return math.nan, math.nan
    z = stats.norm.ppf(1 - alpha / 2)
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return max(0, center - half), min(1, center + half)


def bin_summary(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    keys = ["model", "intervention", "setting", column]
    observed = (
        frame.groupby(keys, observed=True)
        .agg(
            n=("abstained", "size"),
            abstentions=("abstained", "sum"),
            confidence_mean=("confidence", "mean"),
            confidence_min=("confidence", "min"),
            confidence_max=("confidence", "max"),
        )
        .reset_index()
    )
    complete = pd.MultiIndex.from_product(
        [MODELS, INTERVENTIONS, SETTINGS, range(10)], names=keys
    ).to_frame(index=False)
    summary = complete.merge(observed, on=keys, how="left")
    summary["n"] = summary["n"].fillna(0).astype(int)
    summary["abstentions"] = summary["abstentions"].fillna(0).astype(int)
    summary["abstention_rate"] = np.where(
        summary["n"] > 0, summary["abstentions"] / summary["n"], np.nan
    )
    intervals = [
        wilson_interval(int(a), int(n))
        for a, n in zip(summary["abstentions"], summary["n"])
    ]
    summary["ci_low"] = [x[0] for x in intervals]
    summary["ci_high"] = [x[1] for x in intervals]
    summary["bin_label"] = summary[column].map(dict(enumerate(BIN_LABELS)))
    return summary


def bootstrap_spearman(
    confidence: np.ndarray,
    abstained: np.ndarray,
    reps: int,
    rng: np.random.Generator,
) -> tuple[float, float]:
    n = len(confidence)
    if n < 3 or len(np.unique(confidence)) < 2 or len(np.unique(abstained)) < 2:
        return math.nan, math.nan
    values = []
    for _ in range(reps):
        take = rng.integers(0, n, n)
        x, y = confidence[take], abstained[take]
        if len(np.unique(x)) < 2 or len(np.unique(y)) < 2:
            continue
        values.append(stats.spearmanr(x, y).statistic)
    if not values:
        return math.nan, math.nan
    return tuple(np.quantile(values, [0.025, 0.975]))


def correlation_summary(
    frame: pd.DataFrame, reps: int, seed: int
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for keys, group in frame.groupby(["model", "intervention", "setting"], sort=False):
        confidence = group["confidence"].to_numpy(float)
        abstained = group["abstained"].to_numpy(int)
        if len(np.unique(confidence)) >= 2 and len(np.unique(abstained)) >= 2:
            result = stats.spearmanr(confidence, abstained)
            rho, p_value = float(result.statistic), float(result.pvalue)
        else:
            rho, p_value = math.nan, math.nan
        ci_low, ci_high = bootstrap_spearman(
            confidence, abstained, reps=reps, rng=rng
        )
        rows.append(
            {
                "model": keys[0],
                "intervention": keys[1],
                "setting": keys[2],
                "n": len(group),
                "unique_confidence": group["confidence"].nunique(),
                "abstentions": int(group["abstained"].sum()),
                "spearman_rho": rho,
                "p_value": p_value,
                "ci_low": ci_low,
                "ci_high": ci_high,
            }
        )
    return pd.DataFrame(rows)


def calibration_summaries(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    reliability_rows: list[dict] = []
    metric_rows: list[dict] = []
    cohorts = {
        "all_candidates": frame,
        "submitted_only": frame[frame["abstained"] == 0],
    }
    for cohort_name, cohort in cohorts.items():
        cohort = cohort[cohort["candidate_correct"].notna()].copy()
        if cohort.empty:
            continue
        cohort["calibration_bin"] = raw_bin_index(cohort["confidence"])
        for keys, group in cohort.groupby(
            ["model", "intervention", "setting"], sort=False
        ):
            y = group["candidate_correct"].to_numpy(float)
            p = group["confidence"].to_numpy(float)
            brier = float(np.mean((p - y) ** 2))
            ece = 0.0
            for _, bin_group in group.groupby("calibration_bin"):
                ece += len(bin_group) / len(group) * abs(
                    bin_group["confidence"].mean()
                    - bin_group["candidate_correct"].mean()
                )
            metric_rows.append(
                {
                    "cohort": cohort_name,
                    "model": keys[0],
                    "intervention": keys[1],
                    "setting": keys[2],
                    "n": len(group),
                    "mean_confidence": float(np.mean(p)),
                    "candidate_accuracy": float(np.mean(y)),
                    "signed_calibration_gap": float(np.mean(p) - np.mean(y)),
                    "brier_score": brier,
                    "ece_10_bin": float(ece),
                }
            )
            for bin_id in range(10):
                bin_group = group[group["calibration_bin"] == bin_id]
                n = len(bin_group)
                correct = int(bin_group["candidate_correct"].sum()) if n else 0
                low, high = wilson_interval(correct, n)
                reliability_rows.append(
                    {
                        "cohort": cohort_name,
                        "model": keys[0],
                        "intervention": keys[1],
                        "setting": keys[2],
                        "raw_bin": bin_id,
                        "bin_label": BIN_LABELS[bin_id],
                        "n": n,
                        "correct": correct,
                        "mean_confidence": (
                            float(bin_group["confidence"].mean()) if n else math.nan
                        ),
                        "candidate_accuracy": correct / n if n else math.nan,
                        "ci_low": low,
                        "ci_high": high,
                    }
                )
    return pd.DataFrame(metric_rows), pd.DataFrame(reliability_rows)


def confidence_distribution_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, group in frame.groupby(["model", "intervention", "setting"], sort=False):
        q1, median, q3 = group["confidence"].quantile([0.25, 0.5, 0.75])
        rows.append(
            {
                "model": keys[0],
                "intervention": keys[1],
                "setting": keys[2],
                "n": len(group),
                "unique_confidence": group["confidence"].nunique(),
                "mean": group["confidence"].mean(),
                "std": group["confidence"].std(),
                "q1": q1,
                "median": median,
                "q3": q3,
            }
        )
    return pd.DataFrame(rows)


def paired_confidence_shifts(
    frame: pd.DataFrame, reps: int, seed: int
) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 1)
    rows = []
    for model in MODELS:
        for intervention in INTERVENTIONS:
            cell = frame[
                (frame["model"] == model)
                & (frame["intervention"] == intervention)
            ]
            for low, high, label in CONTRASTS:
                a = cell[cell["setting"] == low][["idx", "confidence"]]
                b = cell[cell["setting"] == high][["idx", "confidence"]]
                paired = a.merge(b, on="idx", suffixes=("_low", "_high"))
                differences = (
                    paired["confidence_high"] - paired["confidence_low"]
                ).to_numpy(float)
                if len(differences):
                    boot = np.array(
                        [
                            np.mean(
                                differences[
                                    rng.integers(0, len(differences), len(differences))
                                ]
                            )
                            for _ in range(reps)
                        ]
                    )
                    ci_low, ci_high = np.quantile(boot, [0.025, 0.975])
                else:
                    ci_low = ci_high = math.nan
                rows.append(
                    {
                        "model": model,
                        "intervention": intervention,
                        "contrast": label,
                        "low_setting": low,
                        "high_setting": high,
                        "n_paired": len(differences),
                        "mean_difference": (
                            float(np.mean(differences)) if len(differences) else math.nan
                        ),
                        "median_difference": (
                            float(np.median(differences)) if len(differences) else math.nan
                        ),
                        "ci_low": ci_low,
                        "ci_high": ci_high,
                    }
                )
    return pd.DataFrame(rows)


def logistic_design(frame: pd.DataFrame, interaction: bool = False):
    """Create a fixed GEE mean-model design and retain its Patsy metadata."""
    level_spec = repr(SETTINGS)
    spline = "bs(confidence, df=3, degree=2, include_intercept=False)"
    formula = (
        f"1 + C(setting, levels={level_spec}) * {spline}"
        if interaction
        else f"1 + C(setting, levels={level_spec}) + {spline}"
    )
    matrix = dmatrix(formula, frame, return_type="dataframe")
    return matrix.to_numpy(float), matrix.design_info


def fit_weighted_logistic(
    design: np.ndarray,
    outcome: np.ndarray,
    weights: np.ndarray | None = None,
    ridge: float = 1e-4,
    maxiter: int = 100,
) -> tuple[np.ndarray, bool]:
    """Fast ridge-stabilized IRLS for the working-independence GEE mean model."""
    n, p = design.shape
    weights = np.ones(n) if weights is None else np.asarray(weights, dtype=float)
    penalty = np.eye(p)
    penalty[0, 0] = 0.0
    mean = np.clip(np.average(outcome, weights=weights), 1e-5, 1 - 1e-5)
    beta = np.zeros(p)
    beta[0] = math.log(mean / (1 - mean))

    def objective(candidate: np.ndarray) -> float:
        eta = np.clip(design @ candidate, -35, 35)
        log_likelihood = np.sum(
            weights
            * (
                outcome * -np.logaddexp(0, -eta)
                + (1 - outcome) * -np.logaddexp(0, eta)
            )
        )
        return float(log_likelihood - 0.5 * ridge * candidate @ penalty @ candidate)

    previous = objective(beta)
    converged = False
    for _ in range(maxiter):
        eta = np.clip(design @ beta, -35, 35)
        probability = expit(eta)
        variance = np.maximum(probability * (1 - probability), 1e-8)
        gradient = (
            design.T @ (weights * (outcome - probability))
            - ridge * penalty @ beta
        )
        hessian = (
            design.T @ (design * (weights * variance)[:, None])
            + ridge * penalty
        )
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(hessian, gradient, rcond=None)[0]
        scale = 1.0
        candidate = beta + step
        current = objective(candidate)
        while current < previous and scale > 1 / 1024:
            scale /= 2
            candidate = beta + scale * step
            current = objective(candidate)
        beta = candidate
        if np.max(np.abs(scale * step)) < 1e-8:
            converged = True
            break
        previous = current
    return beta, converged


def design_for_prediction(design_info, frame: pd.DataFrame) -> np.ndarray:
    return np.asarray(build_design_matrices([design_info], frame)[0], dtype=float)


def prepare_prediction_contrast(
    design_info,
    frame: pd.DataFrame,
    clusters: np.ndarray,
    low: str,
    high: str,
) -> dict:
    pair = frame[frame["setting"].isin([low, high])].copy()
    low_values = pair.loc[pair["setting"] == low, "confidence"]
    high_values = pair.loc[pair["setting"] == high, "confidence"]
    overlap_low = max(float(low_values.min()), float(high_values.min()))
    overlap_high = min(float(low_values.max()), float(high_values.max()))
    base = pair[
        pair["confidence"].between(overlap_low, overlap_high, inclusive="both")
    ].copy()
    if base.empty or overlap_low > overlap_high:
        return {
            "low_design": np.empty((0, len(design_info.column_names))),
            "high_design": np.empty((0, len(design_info.column_names))),
            "cluster_codes": np.array([], dtype=int),
            "n": 0,
            "overlap_low": overlap_low,
            "overlap_high": overlap_high,
        }
    low_frame, high_frame = base.copy(), base.copy()
    low_frame["setting"] = low
    high_frame["setting"] = high
    cluster_categories = pd.Categorical(base["idx"], categories=clusters)
    return {
        "low_design": design_for_prediction(design_info, low_frame),
        "high_design": design_for_prediction(design_info, high_frame),
        "cluster_codes": cluster_categories.codes,
        "n": len(base),
        "overlap_low": overlap_low,
        "overlap_high": overlap_high,
    }


def prediction_contrast(
    beta: np.ndarray,
    prepared: dict,
    cluster_counts: np.ndarray | None = None,
) -> float:
    if not prepared["n"]:
        return math.nan
    difference = expit(prepared["high_design"] @ beta) - expit(
        prepared["low_design"] @ beta
    )
    if cluster_counts is None:
        return float(np.mean(difference))
    weights = cluster_counts[prepared["cluster_codes"]]
    if not weights.sum():
        return math.nan
    return float(np.average(difference, weights=weights))


def benjamini_hochberg(values: Sequence[float]) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    out = np.full(len(values), np.nan)
    valid = np.flatnonzero(np.isfinite(values))
    if not len(valid):
        return out
    p = values[valid]
    order = np.argsort(p)
    ranked = p[order]
    adjusted = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    restored = np.empty_like(adjusted)
    restored[order] = np.minimum(adjusted, 1)
    out[valid] = restored
    return out


def adjusted_consequence_contrasts(
    frame: pd.DataFrame, reps: int, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit working-independence logistic GEE means and cluster-bootstrap effects."""
    rng = np.random.default_rng(seed + 2)
    contrast_rows = []
    curve_rows = []

    for model in MODELS:
        for intervention in INTERVENTIONS:
            cell = frame[
                (frame["model"] == model)
                & (frame["intervention"] == intervention)
            ].copy()
            clusters = cell["idx"].drop_duplicates().to_numpy()
            cluster_codes = pd.Categorical(cell["idx"], categories=clusters).codes
            design, design_info = logistic_design(cell, interaction=False)
            outcome = cell["abstained"].to_numpy(float)
            beta, converged = fit_weighted_logistic(design, outcome)
            fit_status = "ok" if converged else "ridge_irls_nonconverged"

            interaction_design, interaction_info = logistic_design(
                cell, interaction=True
            )
            interaction_beta, interaction_converged = fit_weighted_logistic(
                interaction_design, outcome, ridge=1e-3
            )
            if not interaction_converged:
                fit_status += ";interaction_nonconverged"
            grid = np.linspace(
                float(cell["confidence"].min()),
                float(cell["confidence"].max()),
                101,
            )
            curve_models = [
                ("additive_primary", design_info, beta),
                ("interaction_sensitivity", interaction_info, interaction_beta),
            ]
            for curve_model, curve_info, curve_beta in curve_models:
                for setting in SETTINGS:
                    prediction_frame = pd.DataFrame(
                        {"confidence": grid, "setting": setting}
                    )
                    predictions = expit(
                        design_for_prediction(curve_info, prediction_frame)
                        @ curve_beta
                    )
                    for confidence, prediction in zip(grid, predictions):
                        curve_rows.append(
                            {
                                "model": model,
                                "intervention": intervention,
                                "setting": setting,
                                "curve_model": curve_model,
                                "confidence": confidence,
                                "predicted_abstention": float(prediction),
                            }
                        )

            prepared = {
                label: prepare_prediction_contrast(
                    design_info, cell, clusters, low, high
                )
                for low, high, label in CONTRASTS
            }
            point = {
                label: prediction_contrast(beta, prepared[label])
                for _, _, label in CONTRASTS
            }
            boot_values = {label: [] for _, _, label in CONTRASTS}
            failed_bootstraps = 0
            for _ in range(reps):
                sampled = rng.integers(0, len(clusters), len(clusters))
                cluster_counts = np.bincount(
                    sampled, minlength=len(clusters)
                ).astype(float)
                row_weights = cluster_counts[cluster_codes]
                try:
                    boot_beta, _ = fit_weighted_logistic(
                        design, outcome, weights=row_weights
                    )
                    for _, _, label in CONTRASTS:
                        value = prediction_contrast(
                            boot_beta, prepared[label], cluster_counts
                        )
                        if math.isfinite(value):
                            boot_values[label].append(value)
                except Exception:
                    failed_bootstraps += 1

            for low, high, label in CONTRASTS:
                values = boot_values[label]
                if values:
                    ci_low, ci_high = np.quantile(values, [0.025, 0.975])
                    p_value = 2 * min(
                        np.mean(np.asarray(values) <= 0),
                        np.mean(np.asarray(values) >= 0),
                    )
                    p_value = max(p_value, 1 / (len(values) + 1))
                else:
                    ci_low = ci_high = p_value = math.nan
                info = prepared[label]
                contrast_rows.append(
                    {
                        "model": model,
                        "intervention": intervention,
                        "contrast": label,
                        "low_setting": low,
                        "high_setting": high,
                        "adjusted_abstention_difference": point[label],
                        "ci_low": ci_low,
                        "ci_high": ci_high,
                        "bootstrap_p_value": p_value,
                        "common_support_n": info["n"],
                        "overlap_low": info["overlap_low"],
                        "overlap_high": info["overlap_high"],
                        "bootstrap_successes": len(values),
                        "bootstrap_failures": failed_bootstraps,
                        "fit_status": fit_status,
                        "ridge_penalty": 1e-4,
                        "working_correlation": "independence",
                    }
                )

    contrasts = pd.DataFrame(contrast_rows)
    primary = contrasts["intervention"] == 2
    contrasts["bh_q_value_primary_int2"] = math.nan
    contrasts.loc[primary, "bh_q_value_primary_int2"] = benjamini_hochberg(
        contrasts.loc[primary, "bootstrap_p_value"].to_numpy()
    )
    return contrasts, pd.DataFrame(curve_rows)


def decision_theory_summary(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    quant = frame[frame["setting"].isin(QUANT_THRESHOLDS)].copy()
    quant["normative_abstain"] = [
        int(confidence < QUANT_THRESHOLDS[setting])
        for confidence, setting in zip(quant["confidence"], quant["setting"])
    ]
    quant["decision_agreement"] = (
        quant["normative_abstain"] == quant["abstained"]
    ).astype(int)
    quant["under_abstain"] = (
        (quant["normative_abstain"] == 1) & (quant["abstained"] == 0)
    ).astype(int)
    quant["over_abstain"] = (
        (quant["normative_abstain"] == 0) & (quant["abstained"] == 1)
    ).astype(int)

    rows = []
    for keys, group in quant.groupby(["model", "intervention", "setting"], sort=False):
        should_abstain = group[group["normative_abstain"] == 1]
        should_submit = group[group["normative_abstain"] == 0]
        rows.append(
            {
                "model": keys[0],
                "intervention": keys[1],
                "setting": keys[2],
                "threshold": QUANT_THRESHOLDS[keys[2]],
                "n": len(group),
                "agreement_rate": group["decision_agreement"].mean(),
                "should_abstain_n": len(should_abstain),
                "under_abstention_n": int(should_abstain["under_abstain"].sum()),
                "under_abstention_rate": (
                    should_abstain["under_abstain"].mean()
                    if len(should_abstain)
                    else math.nan
                ),
                "should_submit_n": len(should_submit),
                "over_abstention_n": int(should_submit["over_abstain"].sum()),
                "over_abstention_rate": (
                    should_submit["over_abstain"].mean()
                    if len(should_submit)
                    else math.nan
                ),
            }
        )

    switch = quant[
        quant["confidence"].between(
            QUANT_THRESHOLDS["Quant-25"],
            QUANT_THRESHOLDS["Quant-100"],
            inclusive="left",
        )
    ]
    switch_rows = []
    for model in MODELS:
        for intervention in INTERVENTIONS:
            for setting in ("Quant-25", "Quant-100"):
                group = switch[
                    (switch["model"] == model)
                    & (switch["intervention"] == intervention)
                    & (switch["setting"] == setting)
                ]
                abstentions = int(group["abstained"].sum())
                low, high = wilson_interval(abstentions, len(group))
                switch_rows.append(
                    {
                        "model": model,
                        "intervention": intervention,
                        "setting": setting,
                        "n": len(group),
                        "abstentions": abstentions,
                        "abstention_rate": (
                            abstentions / len(group) if len(group) else math.nan
                        ),
                        "ci_low": low,
                        "ci_high": high,
                    }
                )
    return pd.DataFrame(rows), pd.DataFrame(switch_rows)


def switch_region_contrast_summary(switch: pd.DataFrame) -> pd.DataFrame:
    """Descriptive Quant-100 minus Quant-25 contrast in the normative switch band."""
    rows = []
    for model in MODELS:
        for intervention in INTERVENTIONS:
            cell = switch[
                (switch["model"] == model)
                & (switch["intervention"] == intervention)
            ].set_index("setting")
            low = cell.loc["Quant-25"]
            high = cell.loc["Quant-100"]
            if int(low["n"]) and int(high["n"]):
                difference = float(high["abstention_rate"] - low["abstention_rate"])
                ci_low = float(high["ci_low"] - low["ci_high"])
                ci_high = float(high["ci_high"] - low["ci_low"])
                table = [
                    [int(high["abstentions"]), int(high["n"] - high["abstentions"])],
                    [int(low["abstentions"]), int(low["n"] - low["abstentions"])],
                ]
                fisher_p = float(stats.fisher_exact(table).pvalue)
            else:
                difference = ci_low = ci_high = fisher_p = math.nan
            rows.append(
                {
                    "model": model,
                    "intervention": intervention,
                    "quant25_n": int(low["n"]),
                    "quant25_abstentions": int(low["abstentions"]),
                    "quant25_abstention_rate": low["abstention_rate"],
                    "quant100_n": int(high["n"]),
                    "quant100_abstentions": int(high["abstentions"]),
                    "quant100_abstention_rate": high["abstention_rate"],
                    "abstention_difference": difference,
                    "newcombe_ci_low": ci_low,
                    "newcombe_ci_high": ci_high,
                    "fisher_exact_p": fisher_p,
                }
            )
    return pd.DataFrame(rows)


def parse_audit_summary(frame: pd.DataFrame) -> pd.DataFrame:
    return (
        frame.groupby(
            [
                "model",
                "intervention",
                "setting",
                "confidence_parse_status",
                "confidence_parse_route",
                "confidence_normalization",
            ],
            dropna=False,
        )
        .agg(
            n=("idx", "size"),
            abstentions=("abstained", "sum"),
            candidate_answers_graded=("candidate_correct", "count"),
            stored_comparisons=("stored_confidence_match", "count"),
            stored_matches=("stored_confidence_match", "sum"),
        )
        .reset_index()
    )


def _facet_axes(title: str):
    fig, axes = plt.subplots(2, 3, figsize=(14, 8.4), sharex=True, sharey=True)
    fig.suptitle(title, fontsize=15)
    return fig, axes.ravel()


def save_figure(fig, base: Path) -> None:
    fig.tight_layout(rect=(0, 0.075, 1, 0.95))
    fig.savefig(base.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_binned_abstention(
    summary: pd.DataFrame, intervention: int, bin_column: str, output: Path
) -> None:
    label = (
        "verbalized confidence"
        if bin_column == "raw_bin"
        else "within-model confidence percentile"
    )
    fig, axes = _facet_axes(
        f"{INTERVENTION_DISPLAY[intervention]}: abstention vs {label}"
    )
    for ax, model in zip(axes, MODELS):
        cell = summary[
            (summary["model"] == model)
            & (summary["intervention"] == intervention)
        ]
        for setting_index, setting in enumerate(SETTINGS):
            line = cell[(cell["setting"] == setting) & (cell["n"] > 0)].sort_values(
                bin_column
            )
            if line.empty:
                continue
            offset = (setting_index - 1.5) * 1.4
            x = line[bin_column].to_numpy() * 10 + 5 + offset
            y = line["abstention_rate"].to_numpy()
            yerr = np.vstack(
                [y - line["ci_low"].to_numpy(), line["ci_high"].to_numpy() - y]
            )
            yerr = np.maximum(yerr, 0)
            ax.errorbar(
                x,
                y,
                yerr=yerr,
                marker="o",
                ms=4,
                capsize=2,
                lw=1.3,
                linestyle="none",
                color=SETTING_COLORS[setting],
                label=SETTING_DISPLAY[setting],
            )
        ax.set_title(MODEL_DISPLAY[model], fontsize=11)
        ax.set_xlim(-3, 103)
        ax.set_ylim(-0.03, 1.03)
        ax.set_xticks([0, 20, 40, 60, 80, 100])
        ax.grid(alpha=0.25)
    axes[-1].set_visible(False)
    for ax in axes[[0, 3]]:
        ax.set_ylabel("Abstention rate")
    for ax in axes[3:5]:
        ax.set_xlabel(
            "Verbalized confidence (%)"
            if bin_column == "raw_bin"
            else "Confidence percentile (pooled within model/method)"
        )
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False)
    save_figure(fig, output)


def plot_confidence_ecdf(frame: pd.DataFrame, intervention: int, output: Path) -> None:
    fig, axes = _facet_axes(
        f"{INTERVENTION_DISPLAY[intervention]}: verbalized confidence distributions"
    )
    for ax, model in zip(axes, MODELS):
        cell = frame[
            (frame["model"] == model)
            & (frame["intervention"] == intervention)
        ]
        for setting in SETTINGS:
            values = np.sort(cell.loc[cell["setting"] == setting, "confidence"].to_numpy())
            if len(values):
                ax.step(
                    values,
                    np.arange(1, len(values) + 1) / len(values),
                    where="post",
                    color=SETTING_COLORS[setting],
                    label=SETTING_DISPLAY[setting],
                    lw=1.6,
                )
        ax.set_title(MODEL_DISPLAY[model], fontsize=11)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.02)
        ax.grid(alpha=0.25)
    axes[-1].set_visible(False)
    for ax in axes[[0, 3]]:
        ax.set_ylabel("Empirical CDF")
    for ax in axes[3:5]:
        ax.set_xlabel("Verbalized confidence")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False)
    save_figure(fig, output)


def plot_calibration(
    reliability: pd.DataFrame, intervention: int, output: Path
) -> None:
    fig, axes = _facet_axes(
        f"{INTERVENTION_DISPLAY[intervention]}: confidence calibration"
    )
    primary = reliability[
        (reliability["cohort"] == "all_candidates")
        & (reliability["n"] >= 3)
    ]
    for ax, model in zip(axes, MODELS):
        ax.plot([0, 1], [0, 1], ls="--", color="black", lw=1, label="Perfect")
        cell = primary[
            (primary["model"] == model)
            & (primary["intervention"] == intervention)
        ]
        for setting in SETTINGS:
            line = cell[(cell["setting"] == setting) & (cell["n"] > 0)].sort_values(
                "mean_confidence"
            )
            if line.empty:
                continue
            ax.plot(
                line["mean_confidence"],
                line["candidate_accuracy"],
                marker="o",
                ms=4,
                color=SETTING_COLORS[setting],
                label=SETTING_DISPLAY[setting],
            )
        ax.set_title(MODEL_DISPLAY[model], fontsize=11)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.grid(alpha=0.25)
    axes[-1].set_visible(False)
    for ax in axes[[0, 3]]:
        ax.set_ylabel("Empirical candidate accuracy")
    for ax in axes[3:5]:
        ax.set_xlabel("Mean confidence in bin")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, frameon=False)
    save_figure(fig, output)


def plot_adjusted_curves(
    curves: pd.DataFrame, intervention: int, output: Path
) -> None:
    if curves.empty:
        return
    fig, axes = _facet_axes(
        f"{INTERVENTION_DISPLAY[intervention]}: confidence-adjusted abstention "
        "(additive model)"
    )
    for ax, model in zip(axes, MODELS):
        cell = curves[
            (curves["model"] == model)
            & (curves["intervention"] == intervention)
            & (curves["curve_model"] == "additive_primary")
        ]
        for setting in SETTINGS:
            line = cell[cell["setting"] == setting]
            if not line.empty:
                ax.plot(
                    line["confidence"],
                    line["predicted_abstention"],
                    color=SETTING_COLORS[setting],
                    label=SETTING_DISPLAY[setting],
                    lw=1.7,
                )
        ax.set_title(MODEL_DISPLAY[model], fontsize=11)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.grid(alpha=0.25)
    axes[-1].set_visible(False)
    for ax in axes[[0, 3]]:
        ax.set_ylabel("Predicted abstention rate")
    for ax in axes[3:5]:
        ax.set_xlabel("Verbalized confidence")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False)
    save_figure(fig, output)


def plot_adjusted_contrasts(contrasts: pd.DataFrame, output: Path) -> None:
    if contrasts.empty:
        return
    fig, axes = plt.subplots(1, 2, figsize=(13, 7), sharex=True, sharey=True)
    labels = [MODEL_DISPLAY[m] for m in MODELS]
    offsets = {-0.14: "Quant-100 − Quant-25", 0.14: "QP7 − QP6"}
    colors = {
        "Quant-100 − Quant-25": "#d62728",
        "QP7 − QP6": "#9467bd",
    }
    for ax, intervention in zip(axes, INTERVENTIONS):
        cell = contrasts[contrasts["intervention"] == intervention]
        for offset, contrast in offsets.items():
            line = (
                cell[cell["contrast"] == contrast]
                .set_index("model")
                .reindex(MODELS)
            )
            y = np.arange(len(MODELS)) + offset
            x = line["adjusted_abstention_difference"].to_numpy(float)
            low = line["ci_low"].to_numpy(float)
            high = line["ci_high"].to_numpy(float)
            ax.hlines(y, low, high, color=colors[contrast], lw=1.5)
            ax.plot(
                x, y, "o", color=colors[contrast], label=contrast
            )
        ax.axvline(0, color="black", ls="--", lw=1)
        ax.set_title(INTERVENTION_DISPLAY[intervention])
        ax.set_xlabel("Adjusted abstention difference")
        ax.set_yticks(np.arange(len(MODELS)))
        ax.set_yticklabels(labels)
        ax.grid(axis="x", alpha=0.25)
        ax.legend(frameon=False, fontsize=9)
    fig.suptitle("Consequence-setting effect after adjusting for verbalized confidence")
    save_figure(fig, output)


def pct(value: object, digits: int = 1) -> str:
    if value is None or not math.isfinite(float(value)):
        return "—"
    return f"{100 * float(value):.{digits}f}%"


def number(value: object, digits: int = 3) -> str:
    if value is None or not math.isfinite(float(value)):
        return "—"
    return f"{float(value):.{digits}f}"


def markdown_table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def write_report(
    path: Path,
    frame: pd.DataFrame,
    analytic: pd.DataFrame,
    correlations: pd.DataFrame,
    calibration: pd.DataFrame,
    shifts: pd.DataFrame,
    contrasts: pd.DataFrame,
    decision: pd.DataFrame,
    switch: pd.DataFrame,
    switch_contrasts: pd.DataFrame,
) -> None:
    parse_rows = []
    for model in MODELS:
        for intervention in INTERVENTIONS:
            subset = frame[
                (frame["model"] == model)
                & (frame["intervention"] == intervention)
            ]
            parsed = subset["confidence"].notna().sum()
            gradeable = subset["candidate_correct"].notna().sum()
            parse_rows.append(
                [
                    MODEL_DISPLAY[model],
                    f"Int{intervention}",
                    len(subset),
                    parsed,
                    pct(parsed / len(subset)),
                    gradeable,
                    pct(gradeable / len(subset)),
                ]
            )

    correlation_rows = []
    for _, row in correlations.iterrows():
        correlation_rows.append(
            [
                MODEL_DISPLAY[row["model"]],
                f"Int{int(row['intervention'])}",
                row["setting"],
                int(row["n"]),
                number(row["spearman_rho"]),
                f"[{number(row['ci_low'])}, {number(row['ci_high'])}]",
            ]
        )

    primary_cal = calibration[
        (calibration["cohort"] == "submitted_only")
    ].copy()
    calibration_rows = []
    for _, row in primary_cal.iterrows():
        calibration_rows.append(
            [
                MODEL_DISPLAY[row["model"]],
                f"Int{int(row['intervention'])}",
                row["setting"],
                int(row["n"]),
                pct(row["mean_confidence"]),
                pct(row["candidate_accuracy"]),
                pct(row["signed_calibration_gap"]),
                number(row["brier_score"]),
            ]
        )

    contrast_rows = []
    for _, row in contrasts.iterrows():
        contrast_rows.append(
            [
                MODEL_DISPLAY[row["model"]],
                f"Int{int(row['intervention'])}",
                row["contrast"],
                int(row["common_support_n"]),
                pct(row["adjusted_abstention_difference"]),
                f"[{pct(row['ci_low'])}, {pct(row['ci_high'])}]",
                (
                    number(row["bh_q_value_primary_int2"])
                    if int(row["intervention"]) == 2
                    else "exploratory"
                ),
            ]
        )

    under_rows = []
    for _, row in decision.iterrows():
        under_rows.append(
            [
                MODEL_DISPLAY[row["model"]],
                f"Int{int(row['intervention'])}",
                row["setting"],
                int(row["n"]),
                pct(row["agreement_rate"]),
                f"{int(row['under_abstention_n'])}/{int(row['should_abstain_n'])}",
                pct(row["under_abstention_rate"]),
            ]
        )

    shift_rows = []
    for _, row in shifts.iterrows():
        shift_rows.append(
            [
                MODEL_DISPLAY[row["model"]],
                f"Int{int(row['intervention'])}",
                row["contrast"],
                int(row["n_paired"]),
                pct(row["mean_difference"]),
                pct(row["median_difference"]),
                f"[{pct(row['ci_low'])}, {pct(row['ci_high'])}]",
            ]
        )

    switch_rows = []
    for _, row in switch_contrasts.iterrows():
        q25 = (
            f"{int(row['quant25_abstentions'])}/{int(row['quant25_n'])} "
            f"({pct(row['quant25_abstention_rate'])})"
            if int(row["quant25_n"])
            else "0/0 (—)"
        )
        q100 = (
            f"{int(row['quant100_abstentions'])}/{int(row['quant100_n'])} "
            f"({pct(row['quant100_abstention_rate'])})"
            if int(row["quant100_n"])
            else "0/0 (—)"
        )
        switch_rows.append(
            [
                MODEL_DISPLAY[row["model"]],
                f"Int{int(row['intervention'])}",
                q25,
                q100,
                pct(row["abstention_difference"]),
                f"[{pct(row['newcombe_ci_low'])}, "
                f"{pct(row['newcombe_ci_high'])}]",
                number(row["fisher_exact_p"]),
            ]
        )

    primary_correlations = correlations[correlations["intervention"] == 2]
    primary_submitted = calibration[
        (calibration["intervention"] == 2)
        & (calibration["cohort"] == "submitted_only")
    ]
    primary_quant_shifts = shifts[
        (shifts["intervention"] == 2)
        & (shifts["contrast"] == "Quant-100 − Quant-25")
    ]
    primary_quant_contrasts = contrasts[
        (contrasts["intervention"] == 2)
        & (contrasts["contrast"] == "Quant-100 − Quant-25")
    ]
    all_primary_correlations_negative = bool(
        len(primary_correlations)
        and (primary_correlations["spearman_rho"] < 0).all()
    )
    all_primary_correlation_cis_negative = bool(
        len(primary_correlations) and (primary_correlations["ci_high"] < 0).all()
    )
    all_primary_quant_shift_cis_cover_zero = bool(
        len(primary_quant_shifts)
        and (primary_quant_shifts["ci_low"] <= 0).all()
        and (primary_quant_shifts["ci_high"] >= 0).all()
    )
    all_primary_quant_contrast_cis_cover_zero = bool(
        len(primary_quant_contrasts)
        and (primary_quant_contrasts["ci_low"] <= 0).all()
        and (primary_quant_contrasts["ci_high"] >= 0).all()
    )
    key_findings = [
        (
            f"- In the primary multi-turn analysis, all "
            f"**{len(primary_correlations)}** model-by-setting correlations were "
            f"{'negative' if all_primary_correlations_negative else 'not uniformly negative'}"
            f"; Spearman ρ ranged from "
            f"**{number(primary_correlations['spearman_rho'].min())}** to "
            f"**{number(primary_correlations['spearman_rho'].max())}**. "
            f"{'Every problem-bootstrap interval was below zero.' if all_primary_correlation_cis_negative else 'Not every problem-bootstrap interval was below zero.'}"
        ),
        (
            f"- Submitted multi-turn answers remained highly confident: cell-level "
            f"mean confidence ranged from "
            f"**{pct(primary_submitted['mean_confidence'].min())}** to "
            f"**{pct(primary_submitted['mean_confidence'].max())}**, with a median "
            f"confidence−accuracy gap of "
            f"**{pct(primary_submitted['signed_calibration_gap'].median())}**."
        ),
        (
            f"- Because multi-turn confidence was elicited before consequences were "
            f"shown, it should not move systematically with quantitative severity. "
            f"Paired Quant-100−Quant-25 mean shifts ranged from "
            f"**{pct(primary_quant_shifts['mean_difference'].min())}** to "
            f"**{pct(primary_quant_shifts['mean_difference'].max())}**; "
            f"{'all five intervals included zero' if all_primary_quant_shift_cis_cover_zero else 'at least one interval excluded zero'}."
        ),
        (
            f"- After adjusting for verbalized confidence, "
            f"{'all five' if all_primary_quant_contrast_cis_cover_zero else 'not all'} "
            f"multi-turn Quant-100−Quant-25 abstention intervals included zero. "
            f"This is the direct aggregate test of whether higher stated stakes "
            f"changed abstention beyond confidence."
        ),
        (
            "- The narrow confidence band where Quant-25 normatively favors "
            "submission but Quant-100 favors abstention is reported separately below. "
            "Those estimates are descriptive and often based on small samples; they "
            "should qualify, rather than replace, the adjusted aggregate analysis."
        ),
    ]

    lines = [
        "# Omni-MATH verbalized confidence and abstention analysis",
        "",
        "## Key findings",
        "",
        *key_findings,
        "",
        "## Interpretation guide",
        "",
        "Intervention 2 is the primary analysis because confidence was elicited before "
        "the consequence setting was revealed. Intervention 1 is supporting evidence: "
        "its confidence and decision were produced with consequences already visible. "
        "Intervention 1 confidence is reparsed directly from its completion, with the "
        "stored Intervention 4 extraction retained only as an audit field. "
        "Intervention 4 decisions are not used as outcomes.",
        "",
        "A negative confidence–abstention correlation means lower-confidence answers "
        "are more likely to be withheld. This alone does not establish consequence "
        "sensitivity. The adjusted setting contrasts ask whether abstention changes "
        "between consequence settings after controlling for reported confidence. "
        "Positive values mean more abstention in Quant-100 than Quant-25, or in QP7 "
        "than QP6. QP7−QP6 is a content contrast rather than a cardinal severity scale.",
        "",
        "Adjusted contrasts use a working-independence logistic GEE mean model "
        "with a three-degree-of-freedom confidence spline, a weak ridge penalty "
        "for quasi-separation, and problem-cluster bootstrap uncertainty.",
        "",
        "## Rebuttal assessment",
        "",
        "This is substantially stronger than reporting unadjusted abstention rates. "
        "The confidence–abstention curves establish that confidence affects the "
        "decision, while the adjusted setting contrasts test the reviewer's distinct "
        "hypothesis: whether consequence severity changes abstention among answers "
        "with comparable verbalized confidence. The multi-turn protocol is the "
        "cleanest version because confidence is recorded before consequences appear.",
        "",
        "The evidence should nevertheless be stated narrowly. Verbal confidence is a "
        "noisy, potentially strategically reported proxy for the model's latent "
        "belief; observational adjustment cannot prove the absence of internal "
        "consequence awareness. QP6 and QP7 are different qualitative scenarios, not "
        "points on a validated cardinal severity scale. Finally, the switch-band "
        "results show that an aggregate null can coexist with model-specific "
        "sensitivity: DeepSeek changes sharply in that small multi-turn subset, while "
        "Qwen changes in the same direction with wider uncertainty. The defensible "
        "claim is therefore limited aggregate consequence sensitivity conditional on "
        "verbal confidence, alongside clear overconfidence/under-abstention—not "
        "universal consequence blindness.",
        "",
        "## Answer grading",
        "",
        "Accuracy is graded on the candidate answer to which the confidence refers. "
        "For Intervention 1 this is the final committed `ANSWER:` field after any "
        "reasoning delimiter; for Intervention 2 it is `predicted_answer_turn1`. "
        "Each candidate is normalized with the repository's `strip_string` routine "
        "and compared to the Omni-MATH ground truth with its symbolic `math_equal` "
        "grader. The analysis applies a 10-second hard limit per unique pair instead "
        "of the evaluator's load-sensitive one-second nested symbolic limit; the "
        "equivalence rules are unchanged and a timeout remains an ordinary non-match. "
        "Missing candidate parses remain missing. Final post-consequence answers are "
        "not substituted for these candidates.",
        "",
        "## Data and parsing coverage",
        "",
        f"The raw export contains **{len(frame):,}** observations; "
        f"**{len(analytic):,}** have a parsed confidence and a determinate decision.",
        "",
        markdown_table(
            [
                "Model",
                "Method",
                "Rows",
                "Confidence parsed",
                "Parse coverage",
                "Candidate gradeable",
                "Grade coverage",
            ],
            parse_rows,
        ),
        "",
        "## Confidence–abstention correlations",
        "",
        markdown_table(
            ["Model", "Method", "Setting", "N", "Spearman ρ", "95% bootstrap CI"],
            correlation_rows,
        ),
        "",
        "## Confidence of submitted answers and candidate accuracy",
        "",
        "The calibration target is the candidate answer that received the confidence "
        "score, not a potentially revised final response. Rows with an unparsed "
        "candidate are omitted, so the table's N is the number of graded submissions.",
        "",
        markdown_table(
            [
                "Model",
                "Method",
                "Setting",
                "N graded submissions",
                "Mean confidence",
                "Candidate accuracy",
                "Confidence−accuracy",
                "Brier",
            ],
            calibration_rows,
        ),
        "",
        "## Confidence-adjusted consequence contrasts",
        "",
        markdown_table(
            [
                "Model",
                "Method",
                "Contrast",
                "Common-support N",
                "Adjusted Δ abstention",
                "95% cluster-bootstrap CI",
                "Int2 BH q",
            ],
            contrast_rows,
        ),
        "",
        "## Consequence setting and verbalized confidence",
        "",
        "These paired contrasts use matched problem IDs. In Intervention 2, confidence "
        "was elicited before the consequence setting was revealed; consequently these "
        "comparisons are a manipulation check for accidental confidence drift rather "
        "than evidence that the model encoded the hidden consequence.",
        "",
        markdown_table(
            [
                "Model",
                "Method",
                "Contrast",
                "N paired",
                "Mean Δ confidence",
                "Median Δ",
                "95% problem-bootstrap CI",
            ],
            shift_rows,
        ),
        "",
        "## Quantitative decision-rule adherence",
        "",
        "For a risk-neutral decision-maker with calibrated confidence, the submission "
        "thresholds are 25/26 (Quant-25) and 100/101 (Quant-100). "
        "Under-abstention is submission below the corresponding threshold.",
        "",
        markdown_table(
            [
                "Model",
                "Method",
                "Setting",
                "N",
                "Decision agreement",
                "Under-abstain count",
                "Under-abstain rate",
            ],
            under_rows,
        ),
        "",
        "## Quantitative normative switch band",
        "",
        "The switch band is [25/26, 100/101): a calibrated, risk-neutral agent should "
        "submit under Quant-25 and abstain under Quant-100. The interval shown is a "
        "conservative difference interval formed from the two Wilson intervals; "
        "Fisher's exact p-value is descriptive and is not multiplicity-adjusted.",
        "",
        markdown_table(
            [
                "Model",
                "Method",
                "Quant-25 abstain",
                "Quant-100 abstain",
                "Δ abstention",
                "Conservative 95% CI",
                "Fisher p",
            ],
            switch_rows,
        ),
        "",
        "## Additional outputs",
        "",
        "- `confidence_abstention_raw.csv`: traceable row-level data and parser flags.",
        "- `absolute_confidence_bins.csv` and `percentile_confidence_bins.csv`: "
        "the two requested binned abstention views with Wilson intervals.",
        "- `calibration_metrics.csv`: overall and submitted-only calibration.",
        "- `confidence_distribution_shifts.csv`: paired confidence changes across settings.",
        "- `quantitative_switch_region.csv`: behavior in [25/26, 100/101).",
        "- `quantitative_switch_region_contrasts.csv`: descriptive setting contrasts "
        "inside that switch band.",
        "- `confidence_adjusted_curves.csv`: additive primary and confidence-by-setting "
        "interaction sensitivity predictions; figures show the additive primary model.",
        "- `*_sensitivity_no_mixed.csv`: sensitivity results excluding ambiguous "
        "single-turn mixed decisions.",
        "- `plots/`: PNG and PDF versions of all figures.",
        "",
        "All confidence transformations are retained in the raw export. Missing or "
        "ambiguous confidence and candidate-answer parses are not imputed.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(
    output_dir: Path,
    frame: pd.DataFrame,
    analytic: pd.DataFrame,
    raw_bins: pd.DataFrame,
    percentile_bins: pd.DataFrame,
    correlations: pd.DataFrame,
    calibration: pd.DataFrame,
    reliability: pd.DataFrame,
    distributions: pd.DataFrame,
    shifts: pd.DataFrame,
    contrasts: pd.DataFrame,
    curves: pd.DataFrame,
    decision: pd.DataFrame,
    switch: pd.DataFrame,
    switch_contrasts: pd.DataFrame,
    audit: pd.DataFrame,
    sensitivity_bins: pd.DataFrame,
    sensitivity_correlations: pd.DataFrame,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    plots = output_dir / "plots"
    plots.mkdir(parents=True, exist_ok=True)

    exports = {
        "confidence_abstention_raw.csv": frame,
        "confidence_parse_audit.csv": audit,
        "absolute_confidence_bins.csv": raw_bins,
        "percentile_confidence_bins.csv": percentile_bins,
        "confidence_abstention_correlations.csv": correlations,
        "calibration_metrics.csv": calibration,
        "calibration_reliability_bins.csv": reliability,
        "confidence_distributions.csv": distributions,
        "confidence_distribution_shifts.csv": shifts,
        "confidence_adjusted_contrasts.csv": contrasts,
        "confidence_adjusted_curves.csv": curves,
        "quantitative_decision_adherence.csv": decision,
        "quantitative_switch_region.csv": switch,
        "quantitative_switch_region_contrasts.csv": switch_contrasts,
        "absolute_confidence_bins_sensitivity_no_mixed.csv": sensitivity_bins,
        "confidence_abstention_correlations_sensitivity_no_mixed.csv": (
            sensitivity_correlations
        ),
    }
    for name, data in exports.items():
        data.to_csv(output_dir / name, index=False)

    for intervention in INTERVENTIONS:
        plot_binned_abstention(
            raw_bins,
            intervention,
            "raw_bin",
            plots / f"abstention_vs_raw_confidence_int{intervention}",
        )
        plot_binned_abstention(
            percentile_bins,
            intervention,
            "percentile_bin",
            plots / f"abstention_vs_confidence_percentile_int{intervention}",
        )
        plot_confidence_ecdf(
            analytic,
            intervention,
            plots / f"confidence_distribution_by_setting_int{intervention}",
        )
        plot_calibration(
            reliability,
            intervention,
            plots / f"confidence_calibration_int{intervention}",
        )
        plot_adjusted_curves(
            curves,
            intervention,
            plots / f"confidence_adjusted_curves_int{intervention}",
        )
    plot_adjusted_contrasts(
        contrasts, plots / "confidence_adjusted_consequence_contrasts"
    )

    write_report(
        output_dir / "confidence_analysis_summary.md",
        frame,
        analytic,
        correlations,
        calibration,
        shifts,
        contrasts,
        decision,
        switch,
        switch_contrasts,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=REPO_ROOT / "evaluation/output/interventions",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "evaluation/output/interventions/confidence_analysis",
    )
    parser.add_argument("--bootstrap-reps", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260725)
    parser.add_argument(
        "--grade-workers",
        type=int,
        default=min(16, os.cpu_count() or 1),
        help="Parallel workers for timeout-protected symbolic candidate grading.",
    )
    parser.add_argument(
        "--skip-gee",
        action="store_true",
        help="Skip slow adjusted GEE/cluster-bootstrap analysis (for parser smoke tests).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = extract_records(args.input_dir.resolve(), grade_workers=args.grade_workers)
    analytic = add_confidence_bins(analytic_rows(frame))
    raw_bins = bin_summary(analytic, "raw_bin")
    percentile_bins = bin_summary(analytic, "percentile_bin")
    correlations = correlation_summary(analytic, args.bootstrap_reps, args.seed)
    calibration, reliability = calibration_summaries(analytic)
    distributions = confidence_distribution_summary(analytic)
    shifts = paired_confidence_shifts(analytic, args.bootstrap_reps, args.seed)
    if args.skip_gee:
        contrasts = pd.DataFrame(
            columns=[
                "model",
                "intervention",
                "contrast",
                "adjusted_abstention_difference",
                "ci_low",
                "ci_high",
            ]
        )
        curves = pd.DataFrame()
    else:
        contrasts, curves = adjusted_consequence_contrasts(
            analytic, args.bootstrap_reps, args.seed
        )
    decision, switch = decision_theory_summary(analytic)
    switch_contrasts = switch_region_contrast_summary(switch)
    audit = parse_audit_summary(frame)
    sensitivity = add_confidence_bins(analytic_rows(frame, exclude_mixed=True))
    sensitivity_bins = bin_summary(sensitivity, "raw_bin")
    sensitivity_correlations = correlation_summary(
        sensitivity, args.bootstrap_reps, args.seed + 100
    )

    write_outputs(
        args.output_dir.resolve(),
        frame,
        analytic,
        raw_bins,
        percentile_bins,
        correlations,
        calibration,
        reliability,
        distributions,
        shifts,
        contrasts,
        curves,
        decision,
        switch,
        switch_contrasts,
        audit,
        sensitivity_bins,
        sensitivity_correlations,
    )
    print(f"wrote confidence analysis to {args.output_dir.resolve()}")
    print(
        f"rows={len(frame)} analytic={len(analytic)} "
        f"confidence_coverage={len(analytic) / len(frame):.1%}"
    )


if __name__ == "__main__":
    main()
