#!/usr/bin/env python3
"""Analyze baseline abstention using separately elicited Int2 confidence.

The outcome is taken from the simultaneous-consequence baseline rollout.
Confidence is taken from Intervention 2 for the same model, consequence
setting, and Omni-MATH problem.  In Int2, confidence was elicited before the
consequence was revealed.  The two values therefore come from independent
rollouts and confidence is a proxy for the baseline rollout's latent
confidence, not a measurement of the exact baseline candidate answer.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import expit


REPO_ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ["Quant-25", "Quant-100", "QP6", "QP7"]
SETTING_DISPLAY = {
    "Quant-25": r"$r_{25}$",
    "Quant-100": r"$r_{100}$",
    "QP6": "QP6",
    "QP7": "QP7",
}
SETTING_SUFFIX = {
    "Quant-25": "quant_1_0_-25",
    "Quant-100": "quant_1_0_-100",
    "QP6": "QP6",
    "QP7": "QP7",
}
MODEL_DISPLAY = {
    "claude-haiku-4-5": "Claude Haiku 4.5",
    "deepseek-v4-pro": "DeepSeek V4 Pro",
    "gemini-3.1-flash-lite-preview": "Gemini 3.1 Flash Lite",
    "gpt-5.4-nano": "GPT-5.4 Nano",
    "qwen3.5-397b": "Qwen3.5-397B",
}
MODELS = list(MODEL_DISPLAY)
GPT_MODEL = "gpt-5.4-nano"
GPT_BASELINE_PATHS = {
    setting: (
        "evaluation/output/qualitative_quantitative_sweep/"
        f"{GPT_MODEL}_{SETTING_SUFFIX[setting]}/cautious_eval.jsonl"
    )
    for setting in SETTINGS
}
CONTRASTS = [
    ("Quant-25", "Quant-100", "Quant-100 − Quant-25"),
    ("QP6", "QP7", "QP7 − QP6"),
]
QUANT_THRESHOLDS = {"Quant-25": 25 / 26, "Quant-100": 100 / 101}
BIN_LABELS = [f"{10 * index}–{10 * (index + 1)}%" for index in range(10)]
MODEL_COLORS = {
    model: color
    for model, color in zip(
        MODELS, ["#4c78a8", "#f58518", "#54a24b", "#e45756", "#b279a2"]
    )
}


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def read_git_jsonl(ref: str, path: str) -> list[dict]:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def baseline_record(
    row: dict, model: str, setting: str, source_path: str, source_ref: str
) -> dict:
    category = row.get("category", "")
    return {
        "model": model,
        "model_display": MODEL_DISPLAY[model],
        "setting": setting,
        "setting_display": SETTING_DISPLAY[setting],
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
        "baseline_source_ref": source_ref,
        "baseline_source_path": source_path,
    }


def load_baselines(
    baseline_root: Path, gpt_ref: str
) -> tuple[pd.DataFrame, dict[tuple[str, str], set[int]]]:
    records: list[dict] = []
    ids: dict[tuple[str, str], set[int]] = {}
    for model in MODELS:
        for setting in SETTINGS:
            if model == GPT_MODEL:
                source_path = GPT_BASELINE_PATHS[setting]
                rows = read_git_jsonl(gpt_ref, source_path)
                source_ref = gpt_ref
            else:
                source_path = str(
                    baseline_root
                    / f"{model}_{SETTING_SUFFIX[setting]}"
                    / "cautious_eval.jsonl"
                )
                rows = read_jsonl(REPO_ROOT / source_path)
                source_ref = "working-tree"
            ids[(model, setting)] = {int(row["idx"]) for row in rows}
            records.extend(
                baseline_record(row, model, setting, source_path, source_ref)
                for row in rows
            )
    frame = pd.DataFrame.from_records(records)
    if frame.duplicated(["model", "setting", "idx"]).any():
        raise AssertionError("duplicate baseline model/setting/idx rows")
    return frame, ids


def load_int2_confidence(
    path: Path,
) -> tuple[pd.DataFrame, dict[tuple[str, str], set[int]]]:
    frame = pd.read_csv(path)
    frame = frame[
        (frame["intervention"] == 2)
        & frame["model"].isin(MODELS)
        & frame["setting"].isin(SETTINGS)
    ].copy()
    if frame.duplicated(["model", "setting", "idx"]).any():
        raise AssertionError("duplicate Int2 model/setting/idx rows")
    ids = {
        (model, setting): set(
            frame.loc[
                (frame["model"] == model) & (frame["setting"] == setting), "idx"
            ].astype(int)
        )
        for model in MODELS
        for setting in SETTINGS
    }
    keep = [
        "model",
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


def percentile_rank(series: pd.Series) -> pd.Series:
    valid = series.notna()
    result = pd.Series(np.nan, index=series.index, dtype=float)
    if valid.any():
        result.loc[valid] = (
            100
            * (series.loc[valid].rank(method="average") - 0.5)
            / valid.sum()
        )
    return result


def build_cross_rollout_data(
    baseline: pd.DataFrame,
    int2: pd.DataFrame,
    baseline_ids: dict[tuple[str, str], set[int]],
    int2_ids: dict[tuple[str, str], set[int]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    merged = baseline.merge(
        int2,
        on=["model", "setting", "idx"],
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    merged["matched_int2_row"] = merged["_merge"] == "both"
    merged["matched_parsed_int2_confidence"] = merged["int2_confidence"].notna()
    merged = merged.drop(columns="_merge")

    merged["int2_confidence_percentile"] = (
        merged.groupby(["model", "setting"], group_keys=False)[
            "int2_confidence"
        ].apply(percentile_rank)
    )

    question_proxy = (
        int2.groupby(["model", "idx"], as_index=False)
        .agg(
            mean_int2_confidence=("int2_confidence", "mean"),
            int2_confidence_repetitions=("int2_confidence", "count"),
        )
    )
    question_proxy["mean_int2_confidence_percentile"] = (
        question_proxy.groupby("model", group_keys=False)[
            "mean_int2_confidence"
        ].apply(percentile_rank)
    )
    merged = merged.merge(
        question_proxy, on=["model", "idx"], how="left", validate="many_to_one"
    )

    audit_rows = []
    for model in MODELS:
        for setting in SETTINGS:
            base = baseline_ids[(model, setting)]
            confidence = int2_ids[(model, setting)]
            expected = set().union(
                *[
                    baseline_ids[(reference_model, setting)]
                    for reference_model in MODELS
                ],
                *[
                    int2_ids[(reference_model, setting)]
                    for reference_model in MODELS
                ],
            )
            cell = merged[
                (merged["model"] == model) & (merged["setting"] == setting)
            ]
            parsed_ids = set(
                cell.loc[cell["int2_confidence"].notna(), "idx"].astype(int)
            )
            audit_rows.append(
                {
                    "model": model,
                    "model_display": MODEL_DISPLAY[model],
                    "setting": setting,
                    "baseline_expected_n": len(expected),
                    "baseline_n": len(base),
                    "baseline_missing_n": len(expected - base),
                    "baseline_missing_idx": ",".join(
                        map(str, sorted(expected - base))
                    ),
                    "int2_row_n": len(confidence),
                    "int2_parsed_confidence_n": len(parsed_ids),
                    "joined_row_n": len(base & confidence),
                    "joined_parsed_confidence_n": len(base & parsed_ids),
                    "baseline_only_n": len(base - confidence),
                    "baseline_only_idx": ",".join(
                        map(str, sorted(base - confidence))
                    ),
                    "int2_only_n": len(confidence - base),
                    "int2_only_idx": ",".join(
                        map(str, sorted(confidence - base))
                    ),
                }
            )
    return merged, pd.DataFrame(audit_rows)


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    if total <= 0:
        return math.nan, math.nan
    z = stats.norm.ppf(0.975)
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    half = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / total
            + z * z / (4 * total * total)
        )
        / denominator
    )
    return max(0, center - half), min(1, center + half)


def add_bins(
    frame: pd.DataFrame, confidence: str, percentile: str
) -> pd.DataFrame:
    result = frame.copy()
    result["absolute_bin"] = np.clip(
        np.floor(result[confidence].astype(float) * 10).astype(int), 0, 9
    )
    result["percentile_bin"] = np.clip(
        np.floor(result[percentile].astype(float) / 10).astype(int), 0, 9
    )
    return result


def bin_summary(frame: pd.DataFrame, bin_column: str) -> pd.DataFrame:
    rows = []
    for model in MODELS:
        for setting in SETTINGS + ["Pooled"]:
            cell = frame[frame["model"] == model]
            if setting != "Pooled":
                cell = cell[cell["setting"] == setting]
            for bin_index in range(10):
                group = cell[cell[bin_column] == bin_index]
                n = len(group)
                abstentions = int(group["baseline_abstained"].sum())
                low, high = wilson_interval(abstentions, n)
                rows.append(
                    {
                        "model": model,
                        "model_display": MODEL_DISPLAY[model],
                        "setting": setting,
                        "bin_type": bin_column,
                        "bin_index": bin_index,
                        "bin_label": BIN_LABELS[bin_index],
                        "n": n,
                        "abstentions": abstentions,
                        "abstention_rate": abstentions / n if n else math.nan,
                        "ci_low": low,
                        "ci_high": high,
                        "confidence_mean": group["analysis_confidence"].mean(),
                        "confidence_min": group["analysis_confidence"].min(),
                        "confidence_max": group["analysis_confidence"].max(),
                    }
                )
    return pd.DataFrame(rows)


def proxy_summary(
    frame: pd.DataFrame, confidence: str, proxy: str
) -> pd.DataFrame:
    rows = []
    scopes = [
        (model, setting)
        for model in MODELS
        for setting in SETTINGS + ["Pooled"]
    ] + [("All models", "Pooled")]
    for model, setting in scopes:
        group = frame if model == "All models" else frame[frame["model"] == model]
        if setting != "Pooled":
            group = group[group["setting"] == setting]
        group = group[group[confidence].notna()]
        abstained = group[group["baseline_abstained"] == 1]
        submitted = group[group["baseline_abstained"] == 0]
        abstentions = int(group["baseline_abstained"].sum())
        low, high = wilson_interval(abstentions, len(group))
        rows.append(
            {
                "proxy": proxy,
                "model": model,
                "model_display": MODEL_DISPLAY.get(model, model),
                "setting": setting,
                "n": len(group),
                "unique_problems": group["idx"].nunique(),
                "baseline_abstentions": abstentions,
                "baseline_abstention_rate": group["baseline_abstained"].mean(),
                "abstention_ci_low": low,
                "abstention_ci_high": high,
                "mean_confidence": group[confidence].mean(),
                "median_confidence": group[confidence].median(),
                "abstained_mean_confidence": abstained[confidence].mean(),
                "submitted_mean_confidence": submitted[confidence].mean(),
                "abstained_minus_submitted_confidence": (
                    abstained[confidence].mean()
                    - submitted[confidence].mean()
                ),
            }
        )
    return pd.DataFrame(rows)


def lower_confidence_auc(
    confidence: np.ndarray, abstained: np.ndarray
) -> float:
    abstained_confidence = confidence[abstained == 1]
    submitted_confidence = confidence[abstained == 0]
    if not len(abstained_confidence) or not len(submitted_confidence):
        return math.nan
    comparisons = abstained_confidence[:, None] - submitted_confidence[None, :]
    return float(
        np.mean(comparisons < 0) + 0.5 * np.mean(comparisons == 0)
    )


def statistic_pair(
    frame: pd.DataFrame, confidence: str
) -> tuple[float, float]:
    x = frame[confidence].to_numpy(float)
    y = frame["baseline_abstained"].to_numpy(int)
    if len(np.unique(x)) < 2 or len(np.unique(y)) < 2:
        return math.nan, math.nan
    return (
        float(stats.spearmanr(x, y).statistic),
        lower_confidence_auc(x, y),
    )


def bootstrap_statistics(
    frame: pd.DataFrame,
    confidence: str,
    reps: int,
    rng: np.random.Generator,
) -> tuple[float, float, float, float, int]:
    clusters = frame["idx"].drop_duplicates().to_numpy()
    groups = {
        idx: frame.index[frame["idx"] == idx].to_numpy() for idx in clusters
    }
    rho_values: list[float] = []
    auc_values: list[float] = []
    for _ in range(reps):
        sampled = rng.choice(clusters, size=len(clusters), replace=True)
        indices = np.concatenate([groups[idx] for idx in sampled])
        rho, auc = statistic_pair(frame.loc[indices], confidence)
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
    scopes = [
        (model, setting)
        for model in MODELS
        for setting in SETTINGS + ["Pooled"]
    ] + [("All models", "Pooled")]
    for model, setting in scopes:
        group = frame if model == "All models" else frame[frame["model"] == model]
        if setting != "Pooled":
            group = group[group["setting"] == setting]
        group = group[group[confidence].notna()].copy()
        rho, auc = statistic_pair(group, confidence)
        rho_low, rho_high, auc_low, auc_high, successes = bootstrap_statistics(
            group, confidence, reps, rng
        )
        rows.append(
            {
                "proxy": proxy,
                "model": model,
                "model_display": MODEL_DISPLAY.get(model, model),
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


def logistic_design(
    confidence: np.ndarray,
    setting: Iterable[str],
    model: Iterable[str] | None = None,
) -> np.ndarray:
    settings = np.asarray(list(setting))
    columns = [np.ones(len(confidence)), confidence - 0.5]
    columns.extend(
        (settings == value).astype(float) for value in SETTINGS[1:]
    )
    if model is not None:
        models = np.asarray(list(model))
        columns.extend((models == value).astype(float) for value in MODELS[1:])
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
    models: Sequence[str] | None = None,
) -> float:
    low_design = logistic_design(
        confidences, [low] * len(confidences), models
    )
    high_design = logistic_design(
        confidences, [high] * len(confidences), models
    )
    return float(np.mean(expit(high_design @ beta) - expit(low_design @ beta)))


def adjusted_model(
    frame: pd.DataFrame,
    confidence: str,
    proxy: str,
    scope_model: str,
    reps: int,
    seed: int,
) -> tuple[dict, list[dict]]:
    analytic = (
        frame
        if scope_model == "All models"
        else frame[frame["model"] == scope_model]
    )
    analytic = analytic[analytic[confidence].notna()].copy()
    include_model = scope_model == "All models"
    model_values = analytic["model"] if include_model else None
    design = logistic_design(
        analytic[confidence].to_numpy(float),
        analytic["setting"],
        model_values,
    )
    outcome = analytic["baseline_abstained"].to_numpy(float)
    beta, converged = fit_weighted_logistic(design, outcome)
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
            "models": support["model"].tolist() if include_model else None,
            "n": len(support),
            "overlap_low": overlap_low,
            "overlap_high": overlap_high,
        }

    rng = np.random.default_rng(seed)
    boot_or: list[float] = []
    boot_contrasts = {label: [] for _, _, label in CONTRASTS}
    failures = 0
    for _ in range(reps):
        sampled = rng.integers(0, len(clusters), len(clusters))
        counts = np.bincount(sampled, minlength=len(clusters))
        weights = counts[codes].astype(float)
        boot_beta, boot_converged = fit_weighted_logistic(
            design, outcome, weights
        )
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
                    info["models"],
                )
            )

    odds_ci = (
        np.quantile(boot_or, [0.025, 0.975])
        if boot_or
        else [math.nan, math.nan]
    )
    model_row = {
        "proxy": proxy,
        "model": scope_model,
        "model_display": MODEL_DISPLAY.get(scope_model, scope_model),
        "n": len(analytic),
        "unique_problems": len(clusters),
        "abstentions": int(outcome.sum()),
        "odds_ratio_abstention_per_10pp_confidence": math.exp(
            0.1 * beta[1]
        ),
        "ci_low": float(odds_ci[0]),
        "ci_high": float(odds_ci[1]),
        "bootstrap_successes": len(boot_or),
        "bootstrap_failures": failures,
        "fit_status": "ok" if converged else "ridge_irls_nonconverged",
        "fixed_effects": (
            "setting + model" if include_model else "setting"
        ),
    }

    contrast_rows = []
    for low, high, label in CONTRASTS:
        info = prepared[label]
        values = np.asarray(boot_contrasts[label], dtype=float)
        interval = (
            np.quantile(values, [0.025, 0.975])
            if len(values)
            else [math.nan, math.nan]
        )
        point = standardized_contrast(
            beta,
            info["confidence"],
            info["low"],
            info["high"],
            info["models"],
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
                "model": scope_model,
                "model_display": MODEL_DISPLAY.get(scope_model, scope_model),
                "contrast": label,
                "low_setting": low,
                "high_setting": high,
                "adjusted_abstention_difference": point,
                "ci_low": float(interval[0]),
                "ci_high": float(interval[1]),
                "bootstrap_p_value": min(1.0, p_value),
                "common_support_n": info["n"],
                "overlap_low": info["overlap_low"],
                "overlap_high": info["overlap_high"],
                "bootstrap_successes": len(values),
                "bootstrap_failures": failures,
            }
        )
    return model_row, contrast_rows


def adjusted_summaries(
    frame: pd.DataFrame,
    confidence: str,
    proxy: str,
    reps: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    model_rows = []
    contrast_rows = []
    for offset, scope_model in enumerate(MODELS + ["All models"]):
        model_row, model_contrasts = adjusted_model(
            frame,
            confidence,
            proxy,
            scope_model,
            reps,
            seed + offset,
        )
        model_rows.append(model_row)
        contrast_rows.extend(model_contrasts)
    return pd.DataFrame(model_rows), pd.DataFrame(contrast_rows)


def rollout_comparison(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for model in MODELS:
        for setting in SETTINGS:
            group = frame[
                (frame["model"] == model)
                & (frame["setting"] == setting)
                & frame["baseline_outcome_valid"]
                & frame["int2_abstained"].notna()
            ]
            rows.append(
                {
                    "model": model,
                    "model_display": MODEL_DISPLAY[model],
                    "setting": setting,
                    "n_joined": len(group),
                    "baseline_abstentions": int(
                        group["baseline_abstained"].sum()
                    ),
                    "baseline_abstention_rate": group[
                        "baseline_abstained"
                    ].mean(),
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
    for model in MODELS:
        for setting, threshold in QUANT_THRESHOLDS.items():
            group = frame[
                (frame["model"] == model)
                & (frame["setting"] == setting)
                & frame["baseline_outcome_valid"]
                & frame["int2_confidence"].notna()
            ].copy()
            group["proxy_normative_abstain"] = (
                group["int2_confidence"] < threshold
            ).astype(int)
            should = group[group["proxy_normative_abstain"] == 1]
            rows.append(
                {
                    "model": model,
                    "model_display": MODEL_DISPLAY[model],
                    "setting": setting,
                    "threshold": threshold,
                    "n": len(group),
                    "baseline_abstentions": int(
                        group["baseline_abstained"].sum()
                    ),
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


def int2_ece_tables(
    int2: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate standard 10-bin ECE for each model's Int2 candidates."""
    summary_rows = []
    bin_rows = []
    for model in MODELS:
        model_rows = int2[int2["model"] == model]
        valid = model_rows[
            model_rows["int2_confidence"].notna()
            & model_rows["int2_candidate_correct"].notna()
        ].copy()
        valid["calibration_bin"] = np.clip(
            np.floor(valid["int2_confidence"].astype(float) * 10).astype(int),
            0,
            9,
        )
        total = len(valid)
        ece = 0.0
        maximum_gap = 0.0
        for bin_index in range(10):
            group = valid[valid["calibration_bin"] == bin_index]
            n = len(group)
            correct = int(group["int2_candidate_correct"].sum()) if n else 0
            mean_confidence = (
                float(group["int2_confidence"].mean()) if n else math.nan
            )
            candidate_accuracy = correct / n if n else math.nan
            absolute_gap = (
                abs(mean_confidence - candidate_accuracy)
                if n
                else math.nan
            )
            contribution = n / total * absolute_gap if n else 0.0
            ece += contribution
            if n:
                maximum_gap = max(maximum_gap, absolute_gap)
            low, high = wilson_interval(correct, n)
            bin_rows.append(
                {
                    "model": model,
                    "model_display": MODEL_DISPLAY[model],
                    "bin_index": bin_index,
                    "bin_label": BIN_LABELS[bin_index],
                    "n": n,
                    "correct": correct,
                    "mean_confidence": mean_confidence,
                    "candidate_accuracy": candidate_accuracy,
                    "absolute_calibration_gap": absolute_gap,
                    "ece_contribution": contribution,
                    "accuracy_ci_low": low,
                    "accuracy_ci_high": high,
                }
            )
        confidence = valid["int2_confidence"].to_numpy(float)
        correctness = valid["int2_candidate_correct"].to_numpy(float)
        summary_rows.append(
            {
                "model": model,
                "model_display": MODEL_DISPLAY[model],
                "int2_rows": len(model_rows),
                "parsed_confidence_n": int(
                    model_rows["int2_confidence"].notna().sum()
                ),
                "gradeable_candidate_n": int(
                    model_rows["int2_candidate_correct"].notna().sum()
                ),
                "ece_n": total,
                "excluded_from_ece_n": len(model_rows) - total,
                "occupied_bins": valid["calibration_bin"].nunique(),
                "mean_confidence": float(np.mean(confidence)),
                "candidate_accuracy": float(np.mean(correctness)),
                "signed_calibration_gap": float(
                    np.mean(confidence) - np.mean(correctness)
                ),
                "ece_10_equal_width": ece,
                "maximum_calibration_error": maximum_gap,
                "brier_score": float(
                    np.mean((confidence - correctness) ** 2)
                ),
            }
        )
    return pd.DataFrame(summary_rows), pd.DataFrame(bin_rows)


def save_figure(fig: plt.Figure, base: Path) -> None:
    fig.tight_layout(rect=(0, 0.02, 1, 0.98))
    fig.savefig(base.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_bins(
    summary: pd.DataFrame, bin_type: str, output: Path
) -> None:
    fig, axes = plt.subplots(
        len(MODELS), len(SETTINGS), figsize=(14, 15), sharex=True
    )
    for row_index, model in enumerate(MODELS):
        model_data = summary[
            (summary["model"] == model) & summary["setting"].isin(SETTINGS)
        ]
        row_high = min(
            1.0,
            max(
                0.15,
                float(model_data["ci_high"].max(skipna=True)) + 0.05,
            ),
        )
        for column_index, setting in enumerate(SETTINGS):
            ax = axes[row_index, column_index]
            line = summary[
                (summary["model"] == model)
                & (summary["setting"] == setting)
                & (summary["n"] > 0)
            ].sort_values("bin_index")
            x = line["bin_index"].to_numpy() * 10 + 5
            y = line["abstention_rate"].to_numpy(float)
            yerr = np.vstack(
                [
                    y - line["ci_low"].to_numpy(float),
                    line["ci_high"].to_numpy(float) - y,
                ]
            )
            ax.errorbar(
                x,
                y,
                yerr=np.maximum(yerr, 0),
                fmt="o",
                capsize=2,
                color=MODEL_COLORS[model],
            )
            ax.set_xlim(0, 100)
            ax.set_ylim(-0.01, row_high)
            ax.grid(alpha=0.22)
            if row_index == 0:
                ax.set_title(SETTING_DISPLAY[setting])
            if column_index == 0:
                ax.set_ylabel(
                    f"{MODEL_DISPLAY[model]}\nBaseline abstention rate"
                )
            if row_index == len(MODELS) - 1:
                ax.set_xlabel(
                    "Int2 confidence (%)"
                    if bin_type == "absolute_bin"
                    else "Within-cell confidence percentile"
                )
    title = (
        "Baseline abstention vs separately elicited Int2 confidence"
        if bin_type == "absolute_bin"
        else "Baseline abstention vs within-model, within-setting "
        "Int2 confidence percentile"
    )
    fig.suptitle(title, y=0.997)
    save_figure(fig, output)


def plot_pooled_bins(
    summary: pd.DataFrame, bin_type: str, output: Path
) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    for model in MODELS:
        line = summary[
            (summary["model"] == model)
            & (summary["setting"] == "Pooled")
            & (summary["n"] > 0)
        ].sort_values("bin_index")
        ax.plot(
            line["bin_index"] * 10 + 5,
            line["abstention_rate"],
            "o-",
            color=MODEL_COLORS[model],
            label=MODEL_DISPLAY[model],
        )
    ax.set_xlim(0, 100)
    ax.set_ylim(0, max(0.25, ax.get_ylim()[1]))
    ax.set_xlabel(
        "Int2 confidence (%)"
        if bin_type == "absolute_bin"
        else "Within-cell confidence percentile"
    )
    ax.set_ylabel("Baseline abstention rate")
    ax.set_title("Baseline abstention by confidence, settings pooled")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False, ncol=2)
    save_figure(fig, output)


def plot_confidence_by_outcome(frame: pd.DataFrame, output: Path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), sharex=True, sharey=True)
    for ax, model in zip(axes.ravel(), MODELS):
        for outcome, label, color in [
            (0, "Submitted", "#1f77b4"),
            (1, "Abstained", "#d62728"),
        ]:
            values = np.sort(
                frame.loc[
                    (frame["model"] == model)
                    & (frame["baseline_abstained"] == outcome)
                    & frame["int2_confidence"].notna(),
                    "int2_confidence",
                ].to_numpy(float)
            )
            if len(values):
                ax.step(
                    values,
                    np.arange(1, len(values) + 1) / len(values),
                    where="post",
                    color=color,
                    label=f"{label} (n={len(values)})",
                )
        ax.set_title(MODEL_DISPLAY[model])
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, fontsize=8)
    axes.ravel()[-1].axis("off")
    for ax in axes[:, 0]:
        ax.set_ylabel("Empirical cumulative probability")
    for ax in axes[-1, :2]:
        ax.set_xlabel("Setting-matched Int2 confidence")
    fig.suptitle(
        "Cross-rollout Int2 confidence by original baseline decision"
    )
    save_figure(fig, output)


def plot_model_confidence_distributions(
    int2: pd.DataFrame, output: Path
) -> None:
    """Plot all parsed Int2 confidence reports, pooled across settings."""
    fig, axes = plt.subplots(
        2, 3, figsize=(14, 8), sharex=True, sharey=True
    )
    bins = np.linspace(0, 1, 21)
    for ax, model in zip(axes.ravel(), MODELS):
        values = int2.loc[
            (int2["model"] == model) & int2["int2_confidence"].notna(),
            "int2_confidence",
        ].to_numpy(float)
        weights = np.full(len(values), 100 / len(values))
        ax.hist(
            values,
            bins=bins,
            weights=weights,
            color=MODEL_COLORS[model],
            alpha=0.82,
            edgecolor="white",
            linewidth=0.5,
        )
        mean = float(np.mean(values))
        median = float(np.median(values))
        ax.axvline(
            mean,
            color="black",
            linestyle="--",
            linewidth=1.3,
            label=f"Mean: {100 * mean:.1f}%",
        )
        ax.axvline(
            median,
            color="black",
            linestyle=":",
            linewidth=1.3,
            label=f"Median: {100 * median:.1f}%",
        )
        ax.set_title(f"{MODEL_DISPLAY[model]} (n={len(values)})")
        ax.grid(axis="y", alpha=0.22)
        ax.legend(frameon=False, fontsize=8)
    axes.ravel()[-1].axis("off")
    for ax in axes[:, 0]:
        ax.set_ylabel("Share of parsed Int2 rollouts (%)")
    for ax in axes[-1, :2]:
        ax.set_xlabel("Verbalized confidence")
    for ax in axes.ravel()[:-1]:
        ax.set_xlim(0, 1)
        ax.xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    fig.suptitle(
        "Distribution of pre-consequence Int2 confidence by model\n"
        "All four consequence settings pooled"
    )
    save_figure(fig, output)


def plot_adjusted_odds(models: pd.DataFrame, output: Path) -> None:
    data = models[models["proxy"] == "setting_matched"].copy()
    order = MODELS + ["All models"]
    data = data.set_index("model").reindex(order)
    y = np.arange(len(order))
    point = data["odds_ratio_abstention_per_10pp_confidence"].to_numpy(float)
    low = data["ci_low"].to_numpy(float)
    high = data["ci_high"].to_numpy(float)
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.hlines(y, low, high, color="#4c78a8", lw=2)
    ax.plot(point, y, "o", color="#4c78a8")
    ax.axvline(1, color="black", ls="--", lw=1)
    ax.set_xscale("log")
    ax.set_yticks(y)
    ax.set_yticklabels([MODEL_DISPLAY.get(value, value) for value in order])
    ax.set_xlabel("Odds ratio for abstention per +10 confidence points")
    ax.set_title("Confidence–abstention association, adjusted for setting")
    ax.grid(axis="x", alpha=0.25)
    save_figure(fig, output)


def plot_adjusted_contrasts(
    contrasts: pd.DataFrame, output: Path
) -> None:
    data = contrasts[
        (contrasts["proxy"] == "setting_matched")
        & contrasts["model"].isin(MODELS)
    ]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)
    for ax, (_, _, contrast) in zip(axes, CONTRASTS):
        cell = data[data["contrast"] == contrast].set_index("model").reindex(MODELS)
        y = np.arange(len(MODELS))
        point = cell["adjusted_abstention_difference"].to_numpy(float)
        low = cell["ci_low"].to_numpy(float)
        high = cell["ci_high"].to_numpy(float)
        ax.hlines(y, low, high, color="#4c78a8", lw=2)
        ax.plot(point, y, "o", color="#4c78a8")
        ax.axvline(0, color="black", ls="--", lw=1)
        ax.set_yticks(y)
        ax.set_yticklabels([MODEL_DISPLAY[model] for model in MODELS])
        ax.set_xlabel("Adjusted difference in abstention rate")
        ax.set_title(contrast)
        ax.grid(axis="x", alpha=0.25)
    fig.suptitle("Consequence-setting contrasts at common Int2 confidence")
    save_figure(fig, output)


def pct(value: object, digits: int = 1) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{100 * number:.{digits}f}%" if math.isfinite(number) else "—"


def number(value: object, digits: int = 3) -> str:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{result:.{digits}f}" if math.isfinite(result) else "—"


def markdown_table(
    headers: Sequence[str], rows: Iterable[Sequence[object]]
) -> str:
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
    adjusted: pd.DataFrame,
    contrasts: pd.DataFrame,
    adherence: pd.DataFrame,
    ece: pd.DataFrame,
) -> None:
    primary_summary = summaries[
        (summaries["proxy"] == "setting_matched")
        & (summaries["setting"] == "Pooled")
        & summaries["model"].isin(MODELS)
    ]
    primary_correlations = correlations[
        (correlations["proxy"] == "setting_matched")
        & (correlations["setting"] == "Pooled")
        & correlations["model"].isin(MODELS + ["All models"])
    ]
    primary_adjusted = adjusted[
        adjusted["proxy"] == "setting_matched"
    ].set_index("model")
    coverage_rows = [
        [
            row["model_display"],
            row["setting"],
            int(row["baseline_n"]),
            int(row["baseline_missing_n"]),
            int(row["int2_row_n"]),
            int(row["joined_parsed_confidence_n"]),
        ]
        for _, row in audit.iterrows()
    ]
    decision_rows = [
        [
            row["model_display"],
            int(row["n"]),
            f"{int(row['baseline_abstentions'])} "
            f"({pct(row['baseline_abstention_rate'])})",
            pct(row["abstained_mean_confidence"]),
            pct(row["submitted_mean_confidence"]),
            pct(row["abstained_minus_submitted_confidence"]),
        ]
        for _, row in primary_summary.iterrows()
    ]
    association_rows = []
    for _, row in primary_correlations.iterrows():
        adjusted_row = primary_adjusted.loc[row["model"]]
        association_rows.append(
            [
                row["model_display"],
                int(row["n"]),
                int(row["abstentions"]),
                number(row["spearman_rho"]),
                f"[{number(row['rho_ci_low'])}, "
                f"{number(row['rho_ci_high'])}]",
                number(row["lower_confidence_auc"]),
                number(
                    adjusted_row[
                        "odds_ratio_abstention_per_10pp_confidence"
                    ]
                ),
                f"[{number(adjusted_row['ci_low'])}, "
                f"{number(adjusted_row['ci_high'])}]",
            ]
        )
    contrast_rows = [
        [
            row["model_display"],
            row["contrast"],
            int(row["common_support_n"]),
            pct(row["adjusted_abstention_difference"]),
            f"[{pct(row['ci_low'])}, {pct(row['ci_high'])}]",
            number(row["bootstrap_p_value"]),
        ]
        for _, row in contrasts[
            (contrasts["proxy"] == "setting_matched")
            & contrasts["model"].isin(MODELS + ["All models"])
        ].iterrows()
    ]
    adherence_rows = [
        [
            row["model_display"],
            row["setting"],
            int(row["n"]),
            pct(row["threshold"]),
            int(row["should_abstain_n"]),
            f"{int(row['under_abstention_n'])}/"
            f"{int(row['should_abstain_n'])}",
            pct(row["under_abstention_rate"]),
            pct(row["decision_agreement_rate"]),
        ]
        for _, row in adherence.iterrows()
    ]
    ece_rows = [
        [
            row["model_display"],
            int(row["ece_n"]),
            int(row["occupied_bins"]),
            pct(row["mean_confidence"]),
            pct(row["candidate_accuracy"]),
            pct(row["signed_calibration_gap"]),
            pct(row["ece_10_equal_width"]),
        ]
        for _, row in ece.iterrows()
    ]
    aggregate_adherence = (
        adherence.groupby("setting", as_index=False)
        .agg(
            should_abstain_n=("should_abstain_n", "sum"),
            under_abstention_n=("under_abstention_n", "sum"),
        )
        .set_index("setting")
    )
    missing = int(audit["baseline_missing_n"].sum())
    new_sweep_missing = int(
        audit.loc[audit["model"] != GPT_MODEL, "baseline_missing_n"].sum()
    )
    gpt_missing = int(
        audit.loc[audit["model"] == GPT_MODEL, "baseline_missing_n"].sum()
    )
    matched = int(raw["int2_confidence"].notna().sum())
    valid_matched = int(
        (raw["baseline_outcome_valid"] & raw["int2_confidence"].notna()).sum()
    )
    abstentions = int(
        raw.loc[
            raw["baseline_outcome_valid"] & raw["int2_confidence"].notna(),
            "baseline_abstained",
        ].sum()
    )
    lines = [
        "# Baseline abstention paired with pre-consequence Int2 confidence",
        "",
        "## Design",
        "",
        "The outcome is the cautious-evaluator abstention label from the original "
        "baseline rollout, where the consequence and math question were presented "
        "together. Confidence comes from a separate Intervention 2 rollout matched "
        "on model, consequence setting, and Omni-MATH question ID. In Int2, the "
        "candidate answer and confidence were elicited before consequences were "
        "shown. Thus baseline abstentions can be paired with a confidence value.",
        "",
        "This is intentionally a cross-rollout design. Int2 confidence describes an "
        "independently generated candidate, not necessarily the exact candidate the "
        "baseline rollout would have produced. It should be called a "
        "**pre-consequence cross-rollout confidence proxy**, not the baseline "
        "rollout's measured confidence.",
        "",
        "The primary analysis uses setting-matched Int2 confidence. The sensitivity "
        "analysis averages Int2 confidence across settings within each model and "
        "question. Absolute bins are ordinary 10-point confidence intervals. "
        "Percentile bins are computed separately within each model × setting cell, "
        "which removes between-model scale differences and within-model shifts in "
        "the confidence scale across prompts.",
        "",
        "## Coverage",
        "",
        f"- Expected baseline design: 2,000 rollouts (5 models × 4 settings × 100).",
        f"- Available baseline rows: **{len(raw):,}**; missing overall: "
        f"**{missing}** (**{new_sweep_missing}** stopped new-sweep repairs and "
        f"**{gpt_missing}** pre-existing GPT baseline row).",
        f"- Rows with parsed, setting-matched Int2 confidence: **{matched:,}**.",
        f"- Valid matched outcomes used in the primary analysis: "
        f"**{valid_matched:,}**, including **{abstentions} abstentions**.",
        "- Missing rollouts and confidence parse failures are not imputed.",
        "",
        markdown_table(
            [
                "Model",
                "Setting",
                "Baseline N",
                "Missing",
                "Int2 rows",
                "Joined parsed confidence",
            ],
            coverage_rows,
        ),
        "",
        "## Model-level baseline decisions and confidence",
        "",
        markdown_table(
            [
                "Model",
                "N",
                "Baseline abstained",
                "Mean conf., abstained",
                "Mean conf., submitted",
                "Difference",
            ],
            decision_rows,
        ),
        "",
        "## Confidence–abstention association",
        "",
        "Negative Spearman ρ and odds ratios below 1 mean higher proxy confidence "
        "is associated with less baseline abstention. `Lower-confidence AUC` is the "
        "probability that a randomly chosen abstained row has lower confidence than "
        "a submitted row (ties count one-half). Intervals use a problem-cluster "
        "bootstrap. Per-model logistic models include setting fixed effects; the "
        "all-model model includes setting and model fixed effects.",
        "",
        markdown_table(
            [
                "Model",
                "N",
                "Abst.",
                "Spearman ρ",
                "95% CI",
                "Lower-conf. AUC",
                "OR / +10pp",
                "95% CI",
            ],
            association_rows,
        ),
        "",
        "## Int2 confidence calibration",
        "",
        "Expected calibration error (ECE) compares the confidence assigned to the "
        "Int2 candidate with whether that same candidate was correct. We use ten "
        "equal-width raw-confidence bins: `[0%, 10%)`, ..., `[90%, 100%]`. "
        "Within each bin, we take the absolute difference between mean confidence "
        "and candidate accuracy, then average these gaps weighted by bin size. "
        "Lower ECE is better; a positive signed gap means the model is overconfident "
        "on average. Rows without both a parsed confidence and a gradeable candidate "
        "are excluded.",
        "",
        markdown_table(
            [
                "Model",
                "ECE N",
                "Occupied bins",
                "Mean confidence",
                "Candidate accuracy",
                "Signed gap",
                "10-bin ECE",
            ],
            ece_rows,
        ),
        "",
        "This calibration calculation is not cross-rollout: confidence and "
        "correctness refer to the same Int2 candidate. It measures confidence "
        "calibration, not consequence sensitivity or abstention behavior.",
        "",
        "## Confidence-adjusted consequence contrasts",
        "",
        "Positive values mean more baseline abstention under Quant-100 than "
        "Quant-25, or QP7 than QP6, standardized over common confidence support. "
        "QP6 and QP7 are different qualitative consequence scenarios, not points "
        "on a validated one-dimensional severity scale.",
        "",
        markdown_table(
            [
                "Model",
                "Contrast",
                "Support N",
                "Adjusted Δ",
                "95% CI",
                "Bootstrap p",
            ],
            contrast_rows,
        ),
        "",
        "## Quantitative decision-threshold diagnostic",
        "",
        "For a `(+1, 0, −L)` rubric, expected-score maximization submits only "
        "when confidence is at least `L/(L+1)`: 96.15% for Quant-25 and "
        "99.01% for Quant-100. Treating the matched Int2 confidence as if it "
        "were the belief governing the baseline decision, "
        f"**{int(aggregate_adherence.loc['Quant-25', 'under_abstention_n'])}/"
        f"{int(aggregate_adherence.loc['Quant-25', 'should_abstain_n'])} "
        f"({pct(aggregate_adherence.loc['Quant-25', 'under_abstention_n'] / aggregate_adherence.loc['Quant-25', 'should_abstain_n'])})** "
        "proxy-indicated abstentions under Quant-25 and "
        f"**{int(aggregate_adherence.loc['Quant-100', 'under_abstention_n'])}/"
        f"{int(aggregate_adherence.loc['Quant-100', 'should_abstain_n'])} "
        f"({pct(aggregate_adherence.loc['Quant-100', 'under_abstention_n'] / aggregate_adherence.loc['Quant-100', 'should_abstain_n'])})** "
        "under Quant-100 were baseline submissions.",
        "",
        "This is strong diagnostic evidence against a purely confidence-only "
        "explanation, but it is not literal revealed-preference compliance: the "
        "confidence and baseline decision came from independent candidate answers.",
        "",
        markdown_table(
            [
                "Model",
                "Setting",
                "N",
                "Threshold",
                "Proxy says abstain",
                "Baseline submitted",
                "Under-abstention rate",
                "Decision agreement",
            ],
            adherence_rows,
        ),
        "",
        "## Interpretation guardrails",
        "",
        "- This design separates confidence elicitation from the baseline decision, "
        "but it does not identify the exact latent confidence that caused that "
        "baseline decision.",
        "- Sparse abstentions—especially for Claude, DeepSeek, and Gemini—make "
        "model-specific slopes and adjusted consequence contrasts imprecise.",
        "- The all-model Spearman correlation and AUC are unadjusted aggregates and "
        "can reflect between-model confidence-scale differences; the all-model "
        "logistic odds ratio includes model and setting fixed effects and is the "
        "preferred pooled estimate.",
        "- Confidence-bin points with small N should be read with their Wilson "
        "intervals. Within-cell percentile bins remove scale differences but do not "
        "calibrate verbal confidence; tied verbal reports can still leave percentile "
        "bins sparse.",
        "- A residual consequence-setting difference after controlling for this "
        "proxy is evidence against a purely confidence-only explanation, but it "
        "should not be described as a causal effect of severity.",
        "",
        "## Files",
        "",
        "- `baseline_int2_confidence_raw.csv`: row-level baseline outcomes, Int2 "
        "confidence, provenance, match status, and both percentile proxies.",
        "- `join_audit.csv`: cell-level coverage and unmatched IDs.",
        "- `proxy_summaries.csv` and "
        "`confidence_baseline_abstention_correlations.csv`: model/setting and pooled "
        "association tables.",
        "- `absolute_confidence_bins.csv` and `percentile_confidence_bins.csv`: "
        "requested primary binned analyses.",
        "- Files suffixed `_question_mean_sensitivity.csv`: problem-level proxy "
        "sensitivity analysis.",
        "- `confidence_adjusted_model_summary.csv` and "
        "`confidence_adjusted_contrasts.csv`: adjusted estimates.",
        "- `rollout_abstention_comparison.csv`: baseline versus Int2 intervention "
        "outcomes (diagnostic only; Int2 outcome is not used as the primary outcome).",
        "- `quantitative_proxy_decision_adherence.csv`: quantitative-threshold "
        "diagnostic.",
        "- `int2_ece_by_model.csv` and `int2_ece_bins_by_model.csv`: pooled "
        "per-model ECE estimates and their complete bin-level decomposition.",
        "- `plots/int2_confidence_distribution_by_model.*`: per-model confidence "
        "histograms using every parsed Int2 report, with all four settings pooled.",
        "- `plots/`: additional publication-oriented PNG and PDF figures.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-root",
        type=Path,
        default=Path("evaluation/output/qualitative_quantitative_sweep"),
    )
    parser.add_argument(
        "--gpt-baseline-ref", default="origin/louai/base-instruct-ablation"
    )
    parser.add_argument(
        "--int2-confidence-csv",
        type=Path,
        default=Path(
            "evaluation/output/interventions/confidence_analysis/"
            "confidence_abstention_raw.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "evaluation/output/interventions/confidence_analysis/"
            "five_model_baseline_abstention"
        ),
    )
    parser.add_argument("--bootstrap-reps", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260728)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    baseline, baseline_ids = load_baselines(
        args.baseline_root, args.gpt_baseline_ref
    )
    int2, int2_ids = load_int2_confidence(args.int2_confidence_csv)
    raw, audit = build_cross_rollout_data(
        baseline, int2, baseline_ids, int2_ids
    )

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

    absolute_bins = bin_summary(primary, "absolute_bin")
    percentile_bins = bin_summary(primary, "percentile_bin")
    sensitivity_absolute_bins = bin_summary(sensitivity, "absolute_bin")
    sensitivity_percentile_bins = bin_summary(
        sensitivity, "percentile_bin"
    )
    summaries = pd.concat(
        [
            proxy_summary(primary, "int2_confidence", "setting_matched"),
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
                args.seed + 100,
            ),
        ],
        ignore_index=True,
    )
    primary_models, primary_contrasts = adjusted_summaries(
        primary,
        "int2_confidence",
        "setting_matched",
        args.bootstrap_reps,
        args.seed + 200,
    )
    sensitivity_models, sensitivity_contrasts = adjusted_summaries(
        sensitivity,
        "mean_int2_confidence",
        "question_mean",
        args.bootstrap_reps,
        args.seed + 300,
    )
    adjusted = pd.concat(
        [primary_models, sensitivity_models], ignore_index=True
    )
    contrasts = pd.concat(
        [primary_contrasts, sensitivity_contrasts], ignore_index=True
    )
    comparison = rollout_comparison(raw)
    adherence = quantitative_proxy_adherence(raw)
    ece, ece_bins = int2_ece_tables(int2)

    output = args.output_dir
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
        "confidence_adjusted_model_summary.csv": adjusted,
        "confidence_adjusted_contrasts.csv": contrasts,
        "rollout_abstention_comparison.csv": comparison,
        "quantitative_proxy_decision_adherence.csv": adherence,
        "int2_ece_by_model.csv": ece,
        "int2_ece_bins_by_model.csv": ece_bins,
    }
    for name, frame in exports.items():
        frame.to_csv(output / name, index=False)

    plot_bins(
        absolute_bins,
        "absolute_bin",
        plots / "baseline_abstention_vs_int2_confidence",
    )
    plot_bins(
        percentile_bins,
        "percentile_bin",
        plots / "baseline_abstention_vs_int2_confidence_percentile",
    )
    plot_pooled_bins(
        absolute_bins,
        "absolute_bin",
        plots / "pooled_baseline_abstention_vs_int2_confidence",
    )
    plot_pooled_bins(
        percentile_bins,
        "percentile_bin",
        plots / "pooled_baseline_abstention_vs_int2_confidence_percentile",
    )
    plot_confidence_by_outcome(
        primary, plots / "int2_confidence_by_baseline_decision"
    )
    plot_model_confidence_distributions(
        int2, plots / "int2_confidence_distribution_by_model"
    )
    plot_adjusted_odds(
        adjusted, plots / "confidence_adjusted_odds_ratios"
    )
    plot_adjusted_contrasts(
        contrasts, plots / "confidence_adjusted_consequence_contrasts"
    )
    write_report(
        output / "summary.md",
        raw,
        audit,
        summaries,
        correlations,
        adjusted,
        contrasts,
        adherence,
        ece,
    )
    print(f"Wrote analysis to {output.resolve()}")
    print(
        f"baseline_rows={len(raw)} "
        f"matched_confidence={raw['int2_confidence'].notna().sum()} "
        f"valid_primary_rows={len(primary)} "
        f"primary_abstentions={primary['baseline_abstained'].sum()}"
    )


if __name__ == "__main__":
    main()
