# Baseline abstention paired with pre-consequence Int2 confidence

## Design

The outcome is the cautious-evaluator abstention label from the original baseline rollout, where the consequence and math question were presented together. Confidence comes from a separate Intervention 2 rollout matched on model, consequence setting, and Omni-MATH question ID. In Int2, the candidate answer and confidence were elicited before consequences were shown. Thus baseline abstentions can be paired with a confidence value.

This is intentionally a cross-rollout design. Int2 confidence describes an independently generated candidate, not necessarily the exact candidate the baseline rollout would have produced. It should be called a **pre-consequence cross-rollout confidence proxy**, not the baseline rollout's measured confidence.

The primary analysis uses setting-matched Int2 confidence. The sensitivity analysis averages Int2 confidence across settings within each model and question. Absolute bins are ordinary 10-point confidence intervals. Percentile bins are computed separately within each model × setting cell, which removes between-model scale differences and within-model shifts in the confidence scale across prompts.

## Coverage

- Expected baseline design: 2,000 rollouts (5 models × 4 settings × 100).
- Available baseline rows: **1,971**; missing overall: **29** (**28** stopped new-sweep repairs and **1** pre-existing GPT baseline row).
- Rows with parsed, setting-matched Int2 confidence: **1,951**.
- Valid matched outcomes used in the primary analysis: **1,951**, including **54 abstentions**.
- Missing rollouts and confidence parse failures are not imputed.

| Model | Setting | Baseline N | Missing | Int2 rows | Joined parsed confidence |
| --- | --- | --- | --- | --- | --- |
| Claude Haiku 4.5 | Quant-25 | 100 | 0 | 100 | 100 |
| Claude Haiku 4.5 | Quant-100 | 100 | 0 | 100 | 100 |
| Claude Haiku 4.5 | QP6 | 100 | 0 | 100 | 100 |
| Claude Haiku 4.5 | QP7 | 100 | 0 | 100 | 100 |
| DeepSeek V4 Pro | Quant-25 | 94 | 6 | 100 | 93 |
| DeepSeek V4 Pro | Quant-100 | 96 | 4 | 100 | 96 |
| DeepSeek V4 Pro | QP6 | 94 | 6 | 100 | 93 |
| DeepSeek V4 Pro | QP7 | 93 | 7 | 96 | 89 |
| Gemini 3.1 Flash Lite | Quant-25 | 100 | 0 | 100 | 100 |
| Gemini 3.1 Flash Lite | Quant-100 | 100 | 0 | 100 | 100 |
| Gemini 3.1 Flash Lite | QP6 | 100 | 0 | 100 | 100 |
| Gemini 3.1 Flash Lite | QP7 | 100 | 0 | 100 | 100 |
| GPT-5.4 Nano | Quant-25 | 100 | 0 | 100 | 100 |
| GPT-5.4 Nano | Quant-100 | 100 | 0 | 99 | 99 |
| GPT-5.4 Nano | QP6 | 99 | 1 | 100 | 99 |
| GPT-5.4 Nano | QP7 | 100 | 0 | 100 | 100 |
| Qwen3.5-397B | Quant-25 | 98 | 2 | 100 | 97 |
| Qwen3.5-397B | Quant-100 | 99 | 1 | 100 | 98 |
| Qwen3.5-397B | QP6 | 99 | 1 | 100 | 96 |
| Qwen3.5-397B | QP7 | 99 | 1 | 95 | 91 |

## Model-level baseline decisions and confidence

| Model | N | Baseline abstained | Mean conf., abstained | Mean conf., submitted | Difference |
| --- | --- | --- | --- | --- | --- |
| Claude Haiku 4.5 | 400 | 5 (1.2%) | 17.0% | 75.9% | -58.9% |
| DeepSeek V4 Pro | 371 | 6 (1.6%) | 49.0% | 96.8% | -47.8% |
| Gemini 3.1 Flash Lite | 400 | 4 (1.0%) | 98.8% | 95.1% | 3.7% |
| GPT-5.4 Nano | 398 | 21 (5.3%) | 40.3% | 55.1% | -14.8% |
| Qwen3.5-397B | 382 | 18 (4.7%) | 80.2% | 94.0% | -13.8% |

## Confidence–abstention association

Negative Spearman ρ and odds ratios below 1 mean higher proxy confidence is associated with less baseline abstention. `Lower-confidence AUC` is the probability that a randomly chosen abstained row has lower confidence than a submitted row (ties count one-half). Intervals use a problem-cluster bootstrap. Per-model logistic models include setting fixed effects; the all-model model includes setting and model fixed effects.

| Model | N | Abst. | Spearman ρ | 95% CI | Lower-conf. AUC | OR / +10pp | 95% CI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Haiku 4.5 | 400 | 5 | -0.172 | [-0.300, -0.035] | 0.941 | 0.397 | [0.014, 0.938] |
| DeepSeek V4 Pro | 371 | 6 | -0.270 | [-0.428, -0.166] | 0.875 | 0.702 | [0.413, 1.059] |
| Gemini 3.1 Flash Lite | 400 | 4 | 0.007 | [-0.101, 0.076] | 0.485 | 1.630 | [0.974, 11.263] |
| GPT-5.4 Nano | 398 | 21 | -0.103 | [-0.217, 0.025] | 0.632 | 0.832 | [0.641, 1.008] |
| Qwen3.5-397B | 382 | 18 | -0.086 | [-0.243, 0.069] | 0.588 | 0.851 | [0.715, 10.525] |
| All models | 1951 | 54 | -0.106 | [-0.159, -0.048] | 0.677 | 0.792 | [0.737, 0.886] |

## Confidence-adjusted consequence contrasts

Positive values mean more baseline abstention under Quant-100 than Quant-25, or QP7 than QP6, standardized over common confidence support. QP6 and QP7 are different qualitative consequence scenarios, not points on a validated one-dimensional severity scale.

| Model | Contrast | Support N | Adjusted Δ | 95% CI | Bootstrap p |
| --- | --- | --- | --- | --- | --- |
| Claude Haiku 4.5 | Quant-100 − Quant-25 | 198 | -0.4% | [-2.5%, 0.1%] | 0.127 |
| Claude Haiku 4.5 | QP7 − QP6 | 199 | -0.3% | [-3.2%, 0.8%] | 0.492 |
| DeepSeek V4 Pro | Quant-100 − Quant-25 | 189 | -0.9% | [-3.6%, 1.0%] | 0.356 |
| DeepSeek V4 Pro | QP7 − QP6 | 182 | -0.8% | [-3.3%, 3.0%] | 0.633 |
| Gemini 3.1 Flash Lite | Quant-100 − Quant-25 | 198 | -0.0% | [-0.0%, -0.0%] | 0.001 |
| Gemini 3.1 Flash Lite | QP7 − QP6 | 199 | -2.1% | [-5.2%, -0.0%] | 0.041 |
| GPT-5.4 Nano | Quant-100 − Quant-25 | 198 | 1.0% | [-2.1%, 4.6%] | 0.547 |
| GPT-5.4 Nano | QP7 − QP6 | 198 | -8.7% | [-14.6%, -3.3%] | 0.001 |
| Qwen3.5-397B | Quant-100 − Quant-25 | 195 | -3.2% | [-7.2%, -0.0%] | 0.037 |
| Qwen3.5-397B | QP7 − QP6 | 182 | -1.3% | [-6.1%, 3.5%] | 0.553 |
| All models | Quant-100 − Quant-25 | 983 | -0.6% | [-1.7%, 0.3%] | 0.210 |
| All models | QP7 − QP6 | 968 | -2.9% | [-5.0%, -1.0%] | 0.001 |

## Quantitative decision-threshold diagnostic

For a `(+1, 0, −L)` rubric, expected-score maximization submits only when confidence is at least `L/(L+1)`: 96.15% for Quant-25 and 99.01% for Quant-100. Treating the matched Int2 confidence as if it were the belief governing the baseline decision, **209/215 (97.2%)** proxy-indicated abstentions under Quant-25 and **251/259 (96.9%)** under Quant-100 were baseline submissions.

This is strong diagnostic evidence against a purely confidence-only explanation, but it is not literal revealed-preference compliance: the confidence and baseline decision came from independent candidate answers.

| Model | Setting | N | Threshold | Proxy says abstain | Baseline submitted | Under-abstention rate | Decision agreement |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Haiku 4.5 | Quant-25 | 100 | 96.2% | 70 | 69/70 | 98.6% | 31.0% |
| Claude Haiku 4.5 | Quant-100 | 100 | 99.0% | 99 | 98/99 | 99.0% | 2.0% |
| DeepSeek V4 Pro | Quant-25 | 93 | 96.2% | 5 | 4/5 | 80.0% | 94.6% |
| DeepSeek V4 Pro | Quant-100 | 96 | 99.0% | 14 | 13/14 | 92.9% | 86.5% |
| Gemini 3.1 Flash Lite | Quant-25 | 100 | 96.2% | 23 | 23/23 | 100.0% | 77.0% |
| Gemini 3.1 Flash Lite | Quant-100 | 100 | 99.0% | 23 | 23/23 | 100.0% | 77.0% |
| GPT-5.4 Nano | Quant-25 | 100 | 96.2% | 95 | 92/95 | 96.8% | 8.0% |
| GPT-5.4 Nano | Quant-100 | 99 | 99.0% | 99 | 95/99 | 96.0% | 4.0% |
| Qwen3.5-397B | Quant-25 | 97 | 96.2% | 22 | 21/22 | 95.5% | 73.2% |
| Qwen3.5-397B | Quant-100 | 98 | 99.0% | 24 | 22/24 | 91.7% | 76.5% |

## Interpretation guardrails

- This design separates confidence elicitation from the baseline decision, but it does not identify the exact latent confidence that caused that baseline decision.
- Sparse abstentions—especially for Claude, DeepSeek, and Gemini—make model-specific slopes and adjusted consequence contrasts imprecise.
- The all-model Spearman correlation and AUC are unadjusted aggregates and can reflect between-model confidence-scale differences; the all-model logistic odds ratio includes model and setting fixed effects and is the preferred pooled estimate.
- Confidence-bin points with small N should be read with their Wilson intervals. Within-cell percentile bins remove scale differences but do not calibrate verbal confidence; tied verbal reports can still leave percentile bins sparse.
- A residual consequence-setting difference after controlling for this proxy is evidence against a purely confidence-only explanation, but it should not be described as a causal effect of severity.

## Files

- `baseline_int2_confidence_raw.csv`: row-level baseline outcomes, Int2 confidence, provenance, match status, and both percentile proxies.
- `join_audit.csv`: cell-level coverage and unmatched IDs.
- `proxy_summaries.csv` and `confidence_baseline_abstention_correlations.csv`: model/setting and pooled association tables.
- `absolute_confidence_bins.csv` and `percentile_confidence_bins.csv`: requested primary binned analyses.
- Files suffixed `_question_mean_sensitivity.csv`: problem-level proxy sensitivity analysis.
- `confidence_adjusted_model_summary.csv` and `confidence_adjusted_contrasts.csv`: adjusted estimates.
- `rollout_abstention_comparison.csv`: baseline versus Int2 intervention outcomes (diagnostic only; Int2 outcome is not used as the primary outcome).
- `quantitative_proxy_decision_adherence.csv`: quantitative-threshold diagnostic.
- `plots/`: publication-oriented PNG and PDF figures.
