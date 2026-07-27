#!/usr/bin/env python3
"""Pair original GPT-5.4 Nano abstentions with separate Int2 confidence.

The baseline consequence sweep lives on a different Git branch from the
intervention outputs. This script reads those baseline JSONL blobs directly
from a Git ref, joins them to the already-parsed Intervention 2 confidence
export by setting and Omni-MATH ``idx``, and writes a focused cross-rollout
analysis. It performs no model inference.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import expit


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL = "gpt-5.4-nano"
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
BASELINE_PATHS = {
    "Quant-25": (
        "evaluation/output/qualitative_quantitative_sweep/"
        "gpt-5.4-nano_quant_1_0_-25/cautious_eval.jsonl"
    ),
    "Quant-100": (
        "evaluation/output/qualitative_quantitative_sweep/"
        "gpt-5.4-nano_quant_1_0_-100/cautious_eval.jsonl"
    ),
    "QP6": (
        "evaluation/output/qualitative_quantitative_sweep/"
        "gpt-5.4-nano_QP6/cautious_eval.jsonl"
    ),
    "QP7": (
        "evaluation/output/qualitative_quantitative_sweep/"
        "gpt-5.4-nano_QP7/cautious_eval.jsonl"
    ),
}
CONTRASTS = [
    ("Quant-25", "Quant-100", "Quant-100 − Quant-25"),
    ("QP6", "QP7", "QP7 − QP6"),
]
QUANT_THRESHOLDS = {"Quant-25": 25 / 26, "Quant-100": 100 / 101}
BIN_LABELS = [f"{10 * i}–{10 * (i + 1)}%" for i in range(10)]


def read_git_jsonl(ref: str, path: str) -> list[dict]:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def load_baseline(ref: str) -> tuple[pd.DataFrame, dict[str, set[int]]]:
    records = []
    ids: dict[str, set[int]] = {}
    for setting in SETTINGS:
        path = BASELINE_PATHS[setting]
        rows = read_git_jsonl(ref, path)
        ids[setting] = {int(row["idx"]) for row in rows}
        for row in rows:
            category = row.get("category", "")
            records.append(
                {
                    "model": MODEL,
                    "setting": setting,
                    "idx": int(row["idx"]),
                    "difficulty": row.get("difficulty"),
                    "domain": json.dumps(row.get("domain", []), ensure_ascii=False),
                    "source": row.get("source", ""),
                    "ground_truth": row.get("gt", row.get("answer", "")),
                    "baseline_category": category,
                    "baseline_abstained": int(category == "abstained"),
                    "baseline_outcome_valid": category != "indeterminate",
                    "baseline_correct": int(category == "correct"),
                    "baseline_pred": row.get("pred", ""),
                    "baseline_model_generation": row.get("model_generation", ""),
                    "baseline_git_ref": ref,
                    "baseline_source_path": path,
                }
            )
    frame = pd.DataFrame.from_records(records)
    if frame.duplicated(["setting", "idx"]).any():
        raise AssertionError("duplicate baseline setting/idx rows")
    return frame, ids


def load_int2_confidence(path: Path) -> tuple[pd.DataFrame, dict[str, set[int]]]:
    frame = pd.read_csv(path)
    frame = frame[
        (frame["model"] == MODEL)
        & (frame["intervention"] == 2)
        & frame["setting"].isin(SETTINGS)
    ].copy()
    if frame.duplicated(["setting", "idx"]).any():
        raise AssertionError("duplicate Int2 setting/idx rows")
    ids = {
        setting: set(frame.loc[frame["setting"] == setting, "idx"].astype(int))
        for setting in SETTINGS
    }
    keep = [
        "setting",
        "idx",
        "confidence",
        "confidence_raw",
        "confidence_line",
        "confidence_parse_status",
        "confidence_parse_route",
        "confidence_normalization",
        "candidate_answer",
        "candidate_correct",
        "category",
        "abstained",
        "source_path",
    ]
    renamed = frame[keep].rename(
        columns={
            "confidence": "int2_confidence",
            "confidence_raw": "int2_confidence_raw",
            "confidence_line": "int2_confidence_line",
            "confidence_parse_status": "int2_confidence_parse_status",
            "confidence_parse_route": "int2_confidence_parse_route",
            "confidence_normalization": "int2_confidence_normalization",
            "candidate_answer": "int2_candidate_answer",
            "candidate_correct": "int2_candidate_correct",
            "category": "int2_category",
            "abstained": "int2_abstained",
            "source_path": "int2_source_path",
        }
    )
    return renamed, ids


def build_cross_rollout_data(
    baseline: pd.DataFrame,
    int2: pd.DataFrame,
    baseline_ids: dict[str, set[int]],
    int2_ids: dict[str, set[int]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    merged = baseline.merge(
        int2,
        on=["setting", "idx"],
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    merged["matched_int2"] = merged["_merge"] == "both"
    merged = merged.drop(columns="_merge")

    question_proxy = (
        int2.groupby("idx", as_index=False)
        .agg(
            mean_int2_confidence=("int2_confidence", "mean"),
            int2_confidence_repetitions=("int2_confidence", "count"),
        )
    )
    question_proxy["mean_int2_confidence_percentile"] = (
        100
        * (
            question_proxy["mean_int2_confidence"].rank(method="average")
            - 0.5
        )
        / len(question_proxy)
    )
    merged = merged.merge(question_proxy, on="idx", how="left", validate="many_to_one")

    parsed = merged["int2_confidence"].notna()
    merged["int2_confidence_percentile"] = math.nan
    merged.loc[parsed, "int2_confidence_percentile"] = (
        100
        * (
            merged.loc[parsed, "int2_confidence"].rank(method="average")
            - 0.5
        )
        / parsed.sum()
    )

    audit_rows = []
    for setting in SETTINGS:
        base = baseline_ids[setting]
        intervention = int2_ids[setting]
        common = base & intervention
        cell = merged[merged["setting"] == setting]
        audit_rows.append(
            {
                "setting": setting,
                "baseline_n": len(base),
                "int2_n": len(intervention),
                "joined_n": len(common),
                "joined_confidence_n": int(cell["int2_confidence"].notna().sum()),
                "baseline_only_n": len(base - intervention),
                "baseline_only_idx": ",".join(map(str, sorted(base - intervention))),
                "int2_only_n": len(intervention - base),
                "int2_only_idx": ",".join(map(str, sorted(intervention - base))),
            }
        )
    return merged, pd.DataFrame(audit_rows)


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    if total <= 0:
        return math.nan, math.nan
    z = stats.norm.ppf(0.975)
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(
        p * (1 - p) / total + z * z / (4 * total * total)
    ) / denom
    return max(0, center - half), min(1, center + half)


def raw_bin(values: pd.Series) -> pd.Series:
    bins = np.floor(values.astype(float).to_numpy() * 10).astype(int)
    return pd.Series(np.clip(bins, 0, 9), index=values.index)


def add_bins(frame: pd.DataFrame, confidence: str, percentile: str) -> pd.DataFrame:
    out = frame.copy()
    out["raw_bin"] = raw_bin(out[confidence])
    out["percentile_bin"] = np.clip(
        np.floor(out[percentile].astype(float) / 10).astype(int), 0, 9
    )
    return out


def bin_summary(frame: pd.DataFrame, bin_column: str) -> pd.DataFrame:
    observed = (
        frame.groupby(["setting", bin_column])
        .agg(
            n=("baseline_abstained", "size"),
            abstentions=("baseline_abstained", "sum"),
            confidence_mean=("analysis_confidence", "mean"),
            confidence_min=("analysis_confidence", "min"),
            confidence_max=("analysis_confidence", "max"),
        )
        .reset_index()
    )
    complete = pd.MultiIndex.from_product(
        [SETTINGS, range(10)], names=["setting", bin_column]
    ).to_frame(index=False)
    summary = complete.merge(observed, how="left", on=["setting", bin_column])
    summary["n"] = summary["n"].fillna(0).astype(int)
    summary["abstentions"] = summary["abstentions"].fillna(0).astype(int)
    summary["abstention_rate"] = np.where(
        summary["n"] > 0, summary["abstentions"] / summary["n"], np.nan
    )
    intervals = [
        wilson_interval(int(a), int(n))
        for a, n in zip(summary["abstentions"], summary["n"])
    ]
    summary["ci_low"] = [value[0] for value in intervals]
    summary["ci_high"] = [value[1] for value in intervals]
    summary["bin_label"] = summary[bin_column].map(dict(enumerate(BIN_LABELS)))
    return summary


def proxy_summary(frame: pd.DataFrame, confidence: str, proxy: str) -> pd.DataFrame:
    rows = []
    for setting in SETTINGS + ["Pooled"]:
        group = frame if setting == "Pooled" else frame[frame["setting"] == setting]
        group = group[group[confidence].notna()]
        abstained = group[group["baseline_abstained"] == 1]
        submitted = group[group["baseline_abstained"] == 0]
        low, high = wilson_interval(int(group["baseline_abstained"].sum()), len(group))
        rows.append(
            {
                "proxy": proxy,
                "setting": setting,
                "n": len(group),
                "unique_problems": group["idx"].nunique(),
                "baseline_abstentions": int(group["baseline_abstained"].sum()),
                "baseline_abstention_rate": group["baseline_abstained"].mean(),
                "abstention_ci_low": low,
                "abstention_ci_high": high,
                "mean_confidence": group[confidence].mean(),
                "median_confidence": group[confidence].median(),
                "abstained_mean_confidence": abstained[confidence].mean(),
                "submitted_mean_confidence": submitted[confidence].mean(),
                "abstained_minus_submitted_confidence": (
                    abstained[confidence].mean() - submitted[confidence].mean()
                ),
            }
        )
    return pd.DataFrame(rows)


def lower_confidence_auc(confidence: np.ndarray, abstained: np.ndarray) -> float:
    a = confidence[abstained == 1]
    s = confidence[abstained == 0]
    if not len(a) or not len(s):
        return math.nan
    comparisons = a[:, None] - s[None, :]
    return float(np.mean(comparisons < 0) + 0.5 * np.mean(comparisons == 0))


def statistic_pair(frame: pd.DataFrame, confidence: str) -> tuple[float, float]:
    x = frame[confidence].to_numpy(float)
    y = frame["baseline_abstained"].to_numpy(int)
    if len(np.unique(x)) < 2 or len(np.unique(y)) < 2:
        return math.nan, math.nan
    rho = float(stats.spearmanr(x, y).statistic)
    return rho, lower_confidence_auc(x, y)


def bootstrap_statistics(
    frame: pd.DataFrame,
    confidence: str,
    reps: int,
    rng: np.random.Generator,
) -> tuple[float, float, float, float, int]:
    clusters = frame["idx"].drop_duplicates().to_numpy()
    groups = {idx: frame.index[frame["idx"] == idx].to_numpy() for idx in clusters}
    rho_values = []
    auc_values = []
    for _ in range(reps):
        sampled = rng.choice(clusters, size=len(clusters), replace=True)
        indices = np.concatenate([groups[idx] for idx in sampled])
        boot = frame.loc[indices]
        rho, auc = statistic_pair(boot, confidence)
        if math.isfinite(rho):
            rho_values.append(rho)
        if math.isfinite(auc):
            auc_values.append(auc)
    rho_ci = (
        np.quantile(rho_values, [0.025, 0.975])
        if rho_values
        else [math.nan, math.nan]
    )
    auc_ci = (
        np.quantile(auc_values, [0.025, 0.975])
        if auc_values
        else [math.nan, math.nan]
    )
    return (
        float(rho_ci[0]),
        float(rho_ci[1]),
        float(auc_ci[0]),
        float(auc_ci[1]),
        min(len(rho_values), len(auc_values)),
    )


def correlation_summary(
    frame: pd.DataFrame,
    confidence: str,
    proxy: str,
    reps: int,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for setting in SETTINGS + ["Pooled"]:
        group = frame if setting == "Pooled" else frame[frame["setting"] == setting]
        group = group[group[confidence].notna()].copy()
        rho, auc = statistic_pair(group, confidence)
        rho_low, rho_high, auc_low, auc_high, successes = bootstrap_statistics(
            group, confidence, reps, rng
        )
        rows.append(
            {
                "proxy": proxy,
                "setting": setting,
                "n": len(group),
                "unique_problems": group["idx"].nunique(),
                "abstentions": int(group["baseline_abstained"].sum()),
                "spearman_rho": rho,
                "rho_ci_low": rho_low,
                "rho_ci_high": rho_high,
                "lower_confidence_auc": auc,
                "auc_ci_low": auc_low,
                "auc_ci_high": auc_high,
                "bootstrap_successes": successes,
            }
        )
    return pd.DataFrame(rows)


def logistic_design(confidence: np.ndarray, setting: Iterable[str]) -> np.ndarray:
    settings = np.asarray(list(setting))
    columns = [np.ones(len(confidence)), confidence - 0.5]
    columns.extend((settings == value).astype(float) for value in SETTINGS[1:])
    return np.column_stack(columns)


def fit_weighted_logistic(
    design: np.ndarray,
    outcome: np.ndarray,
    row_weights: np.ndarray | None = None,
    ridge: float = 1e-3,
) -> tuple[np.ndarray, bool]:
    weights = np.ones(len(outcome)) if row_weights is None else row_weights
    beta = np.zeros(design.shape[1])
    penalty = np.eye(design.shape[1]) * ridge
    penalty[0, 0] = 0
    converged = False
    for _ in range(100):
        probability = np.clip(expit(design @ beta), 1e-8, 1 - 1e-8)
        working = weights * probability * (1 - probability)
        hessian = design.T @ (working[:, None] * design) + penalty
        gradient = design.T @ (weights * (outcome - probability)) - penalty @ beta
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError:
            step = np.linalg.pinv(hessian) @ gradient
        beta += step
        if np.max(np.abs(step)) < 1e-8:
            converged = True
            break
    return beta, converged


def standardized_contrast(
    beta: np.ndarray,
    confidences: np.ndarray,
    low: str,
    high: str,
) -> float:
    low_design = logistic_design(confidences, [low] * len(confidences))
    high_design = logistic_design(confidences, [high] * len(confidences))
    return float(np.mean(expit(high_design @ beta) - expit(low_design @ beta)))


def adjusted_model(
    frame: pd.DataFrame,
    confidence: str,
    proxy: str,
    reps: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    analytic = frame[frame[confidence].notna()].copy()
    x = logistic_design(
        analytic[confidence].to_numpy(float), analytic["setting"]
    )
    y = analytic["baseline_abstained"].to_numpy(float)
    beta, converged = fit_weighted_logistic(x, y)
    clusters = analytic["idx"].drop_duplicates().to_numpy()
    codes = pd.Categorical(analytic["idx"], categories=clusters).codes

    prepared = {}
    for low, high, label in CONTRASTS:
        pair = analytic[analytic["setting"].isin([low, high])]
        overlap_low = max(
            pair.loc[pair["setting"] == low, confidence].min(),
            pair.loc[pair["setting"] == high, confidence].min(),
        )
        overlap_high = min(
            pair.loc[pair["setting"] == low, confidence].max(),
            pair.loc[pair["setting"] == high, confidence].max(),
        )
        support = pair[pair[confidence].between(overlap_low, overlap_high)]
        prepared[label] = {
            "low": low,
            "high": high,
            "confidence": support[confidence].to_numpy(float),
            "n": len(support),
            "overlap_low": overlap_low,
            "overlap_high": overlap_high,
        }

    rng = np.random.default_rng(seed)
    boot_or = []
    boot_contrasts = {label: [] for _, _, label in CONTRASTS}
    failures = 0
    for _ in range(reps):
        sampled = rng.integers(0, len(clusters), len(clusters))
        counts = np.bincount(sampled, minlength=len(clusters))
        weights = counts[codes].astype(float)
        boot_beta, boot_converged = fit_weighted_logistic(x, y, weights)
        if not boot_converged:
            failures += 1
            continue
        boot_or.append(math.exp(0.1 * boot_beta[1]))
        for _, _, label in CONTRASTS:
            info = prepared[label]
            boot_contrasts[label].append(
                standardized_contrast(
                    boot_beta,
                    info["confidence"],
                    info["low"],
                    info["high"],
                )
            )

    or_ci = (
        np.quantile(boot_or, [0.025, 0.975])
        if boot_or
        else [math.nan, math.nan]
    )
    model_row = pd.DataFrame(
        [
            {
                "proxy": proxy,
                "n": len(analytic),
                "unique_problems": len(clusters),
                "abstentions": int(y.sum()),
                "odds_ratio_abstention_per_10pp_confidence": math.exp(
                    0.1 * beta[1]
                ),
                "ci_low": float(or_ci[0]),
                "ci_high": float(or_ci[1]),
                "bootstrap_successes": len(boot_or),
                "bootstrap_failures": failures,
                "fit_status": "ok" if converged else "ridge_irls_nonconverged",
            }
        ]
    )

    contrast_rows = []
    for low, high, label in CONTRASTS:
        info = prepared[label]
        values = np.asarray(boot_contrasts[label], dtype=float)
        ci_low, ci_high = (
            np.quantile(values, [0.025, 0.975])
            if len(values)
            else [math.nan, math.nan]
        )
        point = standardized_contrast(
            beta, info["confidence"], info["low"], info["high"]
        )
        p_value = (
            2
            * min(
                (np.sum(values <= 0) + 1) / (len(values) + 1),
                (np.sum(values >= 0) + 1) / (len(values) + 1),
            )
            if len(values)
            else math.nan
        )
        contrast_rows.append(
            {
                "proxy": proxy,
                "contrast": label,
                "low_setting": low,
                "high_setting": high,
                "adjusted_abstention_difference": point,
                "ci_low": float(ci_low),
                "ci_high": float(ci_high),
                "bootstrap_p_value": min(1.0, p_value),
                "common_support_n": info["n"],
                "overlap_low": info["overlap_low"],
                "overlap_high": info["overlap_high"],
                "bootstrap_successes": len(values),
                "bootstrap_failures": failures,
            }
        )
    return model_row, pd.DataFrame(contrast_rows)


def rollout_comparison(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for setting in SETTINGS:
        group = frame[
            (frame["setting"] == setting)
            & frame["baseline_outcome_valid"]
            & frame["int2_abstained"].notna()
        ]
        rows.append(
            {
                "setting": setting,
                "n_joined": len(group),
                "baseline_abstentions": int(group["baseline_abstained"].sum()),
                "baseline_abstention_rate": group["baseline_abstained"].mean(),
                "int2_abstentions": int(group["int2_abstained"].sum()),
                "int2_abstention_rate": group["int2_abstained"].mean(),
                "int2_minus_baseline_abstention": (
                    group["int2_abstained"].mean()
                    - group["baseline_abstained"].mean()
                ),
            }
        )
    return pd.DataFrame(rows)


def quantitative_proxy_adherence(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for setting, threshold in QUANT_THRESHOLDS.items():
        group = frame[
            (frame["setting"] == setting) & frame["int2_confidence"].notna()
        ].copy()
        group["proxy_normative_abstain"] = (
            group["int2_confidence"] < threshold
        ).astype(int)
        should = group[group["proxy_normative_abstain"] == 1]
        rows.append(
            {
                "setting": setting,
                "threshold": threshold,
                "n": len(group),
                "baseline_abstentions": int(group["baseline_abstained"].sum()),
                "decision_agreement_rate": (
                    group["baseline_abstained"]
                    == group["proxy_normative_abstain"]
                ).mean(),
                "should_abstain_n": len(should),
                "under_abstention_n": int(
                    (should["baseline_abstained"] == 0).sum()
                ),
                "under_abstention_rate": (
                    (should["baseline_abstained"] == 0).mean()
                    if len(should)
                    else math.nan
                ),
            }
        )
    return pd.DataFrame(rows)


def save_figure(fig, base: Path) -> None:
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    fig.savefig(base.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_bins(summary: pd.DataFrame, bin_column: str, output: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), sharex=True, sharey=True)
    axes = axes.ravel()
    for ax, setting in zip(axes, SETTINGS):
        line = summary[
            (summary["setting"] == setting) & (summary["n"] > 0)
        ].sort_values(bin_column)
        x = line[bin_column].to_numpy() * 10 + 5
        y = line["abstention_rate"].to_numpy(float)
        yerr = np.vstack(
            [y - line["ci_low"].to_numpy(), line["ci_high"].to_numpy() - y]
        )
        ax.errorbar(
            x,
            y,
            yerr=np.maximum(yerr, 0),
            fmt="o",
            capsize=3,
            color=SETTING_COLORS[setting],
        )
        ax.set_title(SETTING_DISPLAY[setting])
        ax.set_xlim(0, 100)
        ax.set_ylim(-0.03, 0.65)
        ax.grid(alpha=0.25)
    for ax in axes[[0, 2]]:
        ax.set_ylabel("Baseline abstention rate")
    for ax in axes[2:]:
        ax.set_xlabel(
            "Matched Int2 confidence (%)"
            if bin_column == "raw_bin"
            else "Matched Int2 confidence percentile"
        )
    title = (
        "Baseline abstention vs separately elicited Int2 confidence"
        if bin_column == "raw_bin"
        else "Baseline abstention vs Int2 confidence percentile"
    )
    fig.suptitle(title)
    save_figure(fig, output)


def plot_rollout_comparison(summary: pd.DataFrame, output: Path) -> None:
    x = np.arange(len(SETTINGS))
    width = 0.36
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.bar(
        x - width / 2,
        summary.set_index("setting").loc[SETTINGS, "baseline_abstention_rate"],
        width,
        label="Original baseline rollout",
        color="#4c78a8",
    )
    ax.bar(
        x + width / 2,
        summary.set_index("setting").loc[SETTINGS, "int2_abstention_rate"],
        width,
        label="Int2 rollout",
        color="#f58518",
    )
    ax.set_xticks(x)
    ax.set_xticklabels([SETTING_DISPLAY[value] for value in SETTINGS])
    ax.set_ylabel("Abstention rate")
    ax.set_ylim(0, 1)
    ax.set_title("Confidence elicitation substantially changes rollout behavior")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.25)
    save_figure(fig, output)


def plot_confidence_by_outcome(
    frame: pd.DataFrame, output: Path
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharex=True, sharey=True)
    specifications = [
        ("int2_confidence", "Setting-matched Int2 confidence"),
        ("mean_int2_confidence", "Question-mean Int2 confidence"),
    ]
    for ax, (column, title) in zip(axes, specifications):
        for outcome, label, color in [
            (0, "Baseline submitted", "#1f77b4"),
            (1, "Baseline abstained", "#d62728"),
        ]:
            values = np.sort(
                frame.loc[
                    (frame["baseline_abstained"] == outcome)
                    & frame[column].notna(),
                    column,
                ].to_numpy(float)
            )
            if len(values):
                ax.step(
                    values,
                    np.arange(1, len(values) + 1) / len(values),
                    where="post",
                    label=f"{label} (n={len(values)})",
                    color=color,
                )
        ax.set_title(title)
        ax.set_xlabel("Confidence")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False)
    axes[0].set_ylabel("Empirical cumulative probability")
    fig.suptitle("Cross-rollout confidence by original baseline decision")
    save_figure(fig, output)


def plot_adjusted_contrasts(contrasts: pd.DataFrame, output: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5))
    proxy_order = ["setting_matched", "question_mean"]
    labels = {
        "setting_matched": "Setting-matched Int2 confidence",
        "question_mean": "Question-mean Int2 confidence",
    }
    colors = {"setting_matched": "#1f77b4", "question_mean": "#9467bd"}
    contrast_order = [value[2] for value in CONTRASTS]
    positions = np.arange(len(contrast_order))
    for offset, proxy in zip([-0.12, 0.12], proxy_order):
        cell = contrasts[contrasts["proxy"] == proxy].set_index("contrast")
        cell = cell.reindex(contrast_order)
        y = positions + offset
        point = cell["adjusted_abstention_difference"].to_numpy(float)
        low = cell["ci_low"].to_numpy(float)
        high = cell["ci_high"].to_numpy(float)
        ax.hlines(y, low, high, color=colors[proxy], lw=1.6)
        ax.plot(point, y, "o", color=colors[proxy], label=labels[proxy])
    ax.axvline(0, color="black", ls="--", lw=1)
    ax.set_yticks(positions)
    ax.set_yticklabels(contrast_order)
    ax.set_xlabel("Confidence-adjusted baseline abstention difference")
    ax.set_title("Original consequence-setting contrasts using Int2 confidence proxy")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(frameon=False)
    save_figure(fig, output)


def pct(value: object, digits: int = 1) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(number):
        return "—"
    return f"{100 * number:.{digits}f}%"


def number(value: object, digits: int = 3) -> str:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(result):
        return "—"
    return f"{result:.{digits}f}"


def markdown_table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(map(str, row)) + " |" for row in rows)
    return "\n".join(lines)


def write_report(
    path: Path,
    raw: pd.DataFrame,
    audit: pd.DataFrame,
    summaries: pd.DataFrame,
    correlations: pd.DataFrame,
    model_summary: pd.DataFrame,
    contrasts: pd.DataFrame,
    comparison: pd.DataFrame,
    adherence: pd.DataFrame,
) -> None:
    primary_summary = summaries[summaries["proxy"] == "setting_matched"]
    primary_corr = correlations[correlations["proxy"] == "setting_matched"]
    primary_model = model_summary[
        model_summary["proxy"] == "setting_matched"
    ].iloc[0]

    coverage_rows = [
        [
            row["setting"],
            int(row["baseline_n"]),
            int(row["int2_n"]),
            int(row["joined_n"]),
            int(row["joined_confidence_n"]),
            row["baseline_only_idx"] or "—",
            row["int2_only_idx"] or "—",
        ]
        for _, row in audit.iterrows()
    ]
    decision_rows = []
    for _, row in primary_summary[
        primary_summary["setting"].isin(SETTINGS)
    ].iterrows():
        decision_rows.append(
            [
                row["setting"],
                int(row["n"]),
                int(row["baseline_abstentions"]),
                pct(row["baseline_abstention_rate"]),
                pct(row["abstained_mean_confidence"]),
                pct(row["submitted_mean_confidence"]),
                pct(row["abstained_minus_submitted_confidence"]),
            ]
        )
    correlation_rows = [
        [
            row["proxy"],
            row["setting"],
            int(row["n"]),
            int(row["abstentions"]),
            number(row["spearman_rho"]),
            f"[{number(row['rho_ci_low'])}, {number(row['rho_ci_high'])}]",
            number(row["lower_confidence_auc"]),
            f"[{number(row['auc_ci_low'])}, {number(row['auc_ci_high'])}]",
        ]
        for _, row in correlations.iterrows()
    ]
    contrast_rows = [
        [
            row["proxy"],
            row["contrast"],
            int(row["common_support_n"]),
            pct(row["adjusted_abstention_difference"]),
            f"[{pct(row['ci_low'])}, {pct(row['ci_high'])}]",
            number(row["bootstrap_p_value"]),
        ]
        for _, row in contrasts.iterrows()
    ]
    comparison_rows = [
        [
            row["setting"],
            int(row["n_joined"]),
            f"{int(row['baseline_abstentions'])} ({pct(row['baseline_abstention_rate'])})",
            f"{int(row['int2_abstentions'])} ({pct(row['int2_abstention_rate'])})",
            pct(row["int2_minus_baseline_abstention"]),
        ]
        for _, row in comparison.iterrows()
    ]
    adherence_rows = [
        [
            row["setting"],
            pct(row["threshold"]),
            int(row["n"]),
            int(row["should_abstain_n"]),
            f"{int(row['under_abstention_n'])}/{int(row['should_abstain_n'])}",
            pct(row["under_abstention_rate"]),
            pct(row["decision_agreement_rate"]),
        ]
        for _, row in adherence.iterrows()
    ]

    pooled = primary_corr[primary_corr["setting"] == "Pooled"].iloc[0]
    lines = [
        "# GPT-5.4 Nano: original abstention paired with Int2 confidence",
        "",
        "## Design",
        "",
        "The outcome is the abstention decision from the original simultaneous-"
        "consequence sweep. The confidence proxy comes from a separate Intervention 2 "
        "rollout of the same model, setting, and Omni-MATH problem. In Intervention 2, "
        "the answer and confidence were generated before consequences were revealed. "
        "No new model inference was performed.",
        "",
        "This design prevents confidence elicitation from causing the baseline "
        "decision and supplies a confidence value even when the baseline rollout "
        "abstained. However, the confidence belongs to the independently generated "
        "Int2 candidate, not necessarily to the exact baseline candidate. It should "
        "therefore be described as a pre-consequence, cross-rollout confidence proxy.",
        "",
        "The primary proxy is the setting-matched Int2 confidence. As a sensitivity "
        "analysis, `question_mean` averages the available consequence-blind Int2 "
        "confidence reports across the four settings for each problem. This reduces "
        "single-draw noise but is even more explicitly a problem-level proxy.",
        "",
        "## Key findings",
        "",
        f"- The setting-matched analysis contains **{int(raw['int2_confidence'].notna().sum())}** "
        f"matched rows and **{int(raw.loc[raw['int2_confidence'].notna(), 'baseline_abstained'].sum())}** "
        "baseline abstentions.",
        f"- Pooled Spearman ρ between the proxy and baseline abstention is "
        f"**{number(pooled['spearman_rho'])}** "
        f"[{number(pooled['rho_ci_low'])}, {number(pooled['rho_ci_high'])}]. "
        "Negative values mean lower Int2 confidence is associated with more baseline "
        "abstention.",
        f"- In a setting-adjusted linear-logit model, the odds ratio for baseline "
        f"abstention per 10-point increase in confidence is "
        f"**{number(primary_model['odds_ratio_abstention_per_10pp_confidence'])}** "
        f"[{number(primary_model['ci_low'])}, {number(primary_model['ci_high'])}].",
        "- Because there are only 21 baseline abstentions, condition-specific and "
        "confidence-adjusted severity estimates are imprecise and should be presented "
        "with their intervals rather than as definitive null effects.",
        "",
        "## Join coverage",
        "",
        markdown_table(
            [
                "Setting",
                "Baseline N",
                "Int2 N",
                "Joined N",
                "Confidence N",
                "Baseline-only idx",
                "Int2-only idx",
            ],
            coverage_rows,
        ),
        "",
        "## Baseline decisions and cross-rollout confidence",
        "",
        markdown_table(
            [
                "Setting",
                "N",
                "Baseline abstained",
                "Abstention rate",
                "Mean confidence: abstained",
                "Mean confidence: submitted",
                "Abstained−submitted",
            ],
            decision_rows,
        ),
        "",
        "## Confidence–baseline-abstention association",
        "",
        "`lower_confidence_auc` is the probability that a randomly chosen baseline-"
        "abstained problem has lower proxy confidence than a randomly chosen submitted "
        "problem, with ties receiving half credit.",
        "",
        markdown_table(
            [
                "Proxy",
                "Setting",
                "N",
                "Abstentions",
                "Spearman ρ",
                "95% CI",
                "Lower-confidence AUC",
                "95% CI",
            ],
            correlation_rows,
        ),
        "",
        "## Confidence-adjusted consequence contrasts",
        "",
        "Positive differences mean more baseline abstention under Quant-100 than "
        "Quant-25, or under QP7 than QP6, at the same proxy-confidence distribution.",
        "The quantitative pair changes a cardinal penalty magnitude. QP6 and QP7 are "
        "different qualitative scenarios, so their contrast is a consequence-setting "
        "comparison—not an estimate of a one-dimensional severity dose response.",
        "",
        markdown_table(
            [
                "Proxy",
                "Contrast",
                "Common-support N",
                "Adjusted Δ abstention",
                "95% cluster-bootstrap CI",
                "Bootstrap p",
            ],
            contrast_rows,
        ),
        "",
        "## Original versus Int2 rollout behavior",
        "",
        markdown_table(
            [
                "Setting",
                "Joined N",
                "Original abstained",
                "Int2 abstained",
                "Int2−original",
            ],
            comparison_rows,
        ),
        "",
        "The large differences above are why Int2 abstention should not be substituted "
        "for the original outcome when answering the reviewer's question.",
        "",
        "## Quantitative proxy decision adherence",
        "",
        "These calculations treat Int2 confidence as if it were the belief governing "
        "the original quantitative decision. Because it is cross-rollout confidence, "
        "this is a diagnostic proxy rather than literal decision-theoretic compliance.",
        "",
        markdown_table(
            [
                "Setting",
                "Threshold",
                "N",
                "Proxy says abstain",
                "Original under-abstained",
                "Under-abstention rate",
                "Agreement",
            ],
            adherence_rows,
        ),
        "",
        "## Files",
        "",
        "- `baseline_int2_confidence_raw.csv`: all 399 original baseline rows, "
        "including the unmatched Quant-100 row.",
        "- `join_audit.csv`: exact overlap and missing problem IDs.",
        "- `proxy_summaries.csv` and `confidence_baseline_abstention_correlations.csv`: "
        "setting-matched and question-mean results.",
        "- `absolute_confidence_bins.csv` and `percentile_confidence_bins.csv`: "
        "requested binned views for the primary setting-matched proxy.",
        "- `confidence_adjusted_contrasts.csv`: consequence-setting contrasts for "
        "both proxies.",
        "- `plots/`: PNG and PDF figures.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-ref", default="origin/louai/base-instruct-ablation"
    )
    parser.add_argument(
        "--int2-confidence-csv",
        type=Path,
        default=(
            REPO_ROOT
            / "evaluation/output/interventions/confidence_analysis/"
            "confidence_abstention_raw.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            REPO_ROOT
            / "evaluation/output/interventions/confidence_analysis/"
            "gpt5nano_baseline_abstention"
        ),
    )
    parser.add_argument("--bootstrap-reps", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260726)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    baseline, baseline_ids = load_baseline(args.baseline_ref)
    int2, int2_ids = load_int2_confidence(args.int2_confidence_csv.resolve())
    raw, audit = build_cross_rollout_data(
        baseline, int2, baseline_ids, int2_ids
    )
    if len(raw) != 399:
        raise AssertionError(f"expected 399 baseline rows, found {len(raw)}")
    if raw["int2_confidence"].notna().sum() != 398:
        raise AssertionError("expected 398 setting-matched confidence rows")

    primary = raw[
        raw["baseline_outcome_valid"] & raw["int2_confidence"].notna()
    ].copy()
    primary["analysis_confidence"] = primary["int2_confidence"]
    primary = add_bins(
        primary, "int2_confidence", "int2_confidence_percentile"
    )
    sensitivity = raw[
        raw["baseline_outcome_valid"] & raw["mean_int2_confidence"].notna()
    ].copy()
    sensitivity["analysis_confidence"] = sensitivity["mean_int2_confidence"]
    sensitivity = add_bins(
        sensitivity,
        "mean_int2_confidence",
        "mean_int2_confidence_percentile",
    )

    absolute_bins = bin_summary(primary, "raw_bin")
    percentile_bins = bin_summary(primary, "percentile_bin")
    sensitivity_absolute_bins = bin_summary(sensitivity, "raw_bin")
    sensitivity_percentile_bins = bin_summary(sensitivity, "percentile_bin")
    summaries = pd.concat(
        [
            proxy_summary(
                primary, "int2_confidence", "setting_matched"
            ),
            proxy_summary(
                sensitivity, "mean_int2_confidence", "question_mean"
            ),
        ],
        ignore_index=True,
    )
    correlations = pd.concat(
        [
            correlation_summary(
                primary,
                "int2_confidence",
                "setting_matched",
                args.bootstrap_reps,
                args.seed,
            ),
            correlation_summary(
                sensitivity,
                "mean_int2_confidence",
                "question_mean",
                args.bootstrap_reps,
                args.seed + 1,
            ),
        ],
        ignore_index=True,
    )
    primary_model, primary_contrasts = adjusted_model(
        primary,
        "int2_confidence",
        "setting_matched",
        args.bootstrap_reps,
        args.seed + 2,
    )
    sensitivity_model, sensitivity_contrasts = adjusted_model(
        sensitivity,
        "mean_int2_confidence",
        "question_mean",
        args.bootstrap_reps,
        args.seed + 3,
    )
    model_summary = pd.concat(
        [primary_model, sensitivity_model], ignore_index=True
    )
    contrasts = pd.concat(
        [primary_contrasts, sensitivity_contrasts], ignore_index=True
    )
    comparison = rollout_comparison(raw)
    adherence = quantitative_proxy_adherence(raw)

    output = args.output_dir.resolve()
    plots = output / "plots"
    plots.mkdir(parents=True, exist_ok=True)
    exports = {
        "baseline_int2_confidence_raw.csv": raw,
        "join_audit.csv": audit,
        "proxy_summaries.csv": summaries,
        "confidence_baseline_abstention_correlations.csv": correlations,
        "absolute_confidence_bins.csv": absolute_bins,
        "percentile_confidence_bins.csv": percentile_bins,
        "absolute_confidence_bins_question_mean_sensitivity.csv": (
            sensitivity_absolute_bins
        ),
        "percentile_confidence_bins_question_mean_sensitivity.csv": (
            sensitivity_percentile_bins
        ),
        "confidence_adjusted_model_summary.csv": model_summary,
        "confidence_adjusted_contrasts.csv": contrasts,
        "rollout_abstention_comparison.csv": comparison,
        "quantitative_proxy_decision_adherence.csv": adherence,
    }
    for name, frame in exports.items():
        frame.to_csv(output / name, index=False)

    plot_bins(
        absolute_bins,
        "raw_bin",
        plots / "baseline_abstention_vs_int2_confidence",
    )
    plot_bins(
        percentile_bins,
        "percentile_bin",
        plots / "baseline_abstention_vs_int2_confidence_percentile",
    )
    plot_rollout_comparison(
        comparison, plots / "baseline_vs_int2_abstention"
    )
    plot_confidence_by_outcome(
        raw, plots / "int2_confidence_by_baseline_decision"
    )
    plot_adjusted_contrasts(
        contrasts, plots / "baseline_confidence_adjusted_contrasts"
    )
    write_report(
        output / "summary.md",
        raw,
        audit,
        summaries,
        correlations,
        model_summary,
        contrasts,
        comparison,
        adherence,
    )
    print(f"wrote cross-rollout analysis to {output}")
    print(
        f"baseline_rows={len(raw)} matched_confidence="
        f"{raw['int2_confidence'].notna().sum()} "
        f"baseline_abstentions={raw['baseline_abstained'].sum()}"
    )


if __name__ == "__main__":
    main()
